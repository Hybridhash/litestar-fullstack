import htmx from "htmx.org"
import { registerHtmxExtension } from "litestar-vite-plugin/helpers"
import Alpine from "@alpinejs/csp"

window.htmx = htmx
window.Alpine = Alpine

const csrfErrorMessage = "CSRF validation failed. Please refresh the page and try again."
const csrfCookieName = "XSRF-TOKEN"
const csrfHeaderName = "X-XSRF-TOKEN"
const unsafeVerbs = new Set(["POST", "PUT", "PATCH", "DELETE"])
const swappableClientErrors = new Set([400, 404, 409, 422, 429])
const userAgent = window.navigator?.userAgent || ""
const isFirefoxIOS = /FxiOS/i.test(userAgent)
const isIOS = /iPhone|iPad|iPod/i.test(userAgent)
const registerFormState = new WeakMap()

// Mobile browsers can evict HTMX history snapshots aggressively; forcing a
// reload on cache misses keeps browser back/forward navigation reliable.
htmx.config.refreshOnHistoryMiss = true
htmx.config.historyCacheSize = Math.max(htmx.config.historyCacheSize || 0, 20)
htmx.config.includeIndicatorStyles = false
htmx.config.allowEval = false
htmx.config.allowScriptTags = false
htmx.config.selfRequestsOnly = true

const readCookie = (name) => {
  if (!document?.cookie) {
    return null
  }
  const parts = document.cookie.split(";")
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed.startsWith(`${name}=`)) {
      continue
    }
    return decodeURIComponent(trimmed.substring(name.length + 1))
  }
  return null
}

const readCsrfToken = () => {
  const cookieToken = readCookie(csrfCookieName)
  if (cookieToken) {
    return cookieToken
  }
  const meta = document.querySelector('meta[name="csrf-token"]')
  return meta?.getAttribute("content") || null
}

const toastShell = () => document.getElementById("toast-shell")

const showToast = (message, variant = "error", timeoutMs = 5000) => {
  const container = toastShell()
  if (!container) {
    return
  }
  const alert = document.createElement("div")
  alert.className = `alert alert-${variant}`
  alert.setAttribute("role", "alert")
  const span = document.createElement("span")
  span.textContent = message
  alert.appendChild(span)
  container.appendChild(alert)
  window.setTimeout(() => {
    alert.remove()
  }, timeoutMs)
}

const isSwappableClientResponse = (xhr) => {
  const contentType = xhr?.getResponseHeader?.("content-type") || ""
  if (contentType.includes("application/json")) {
    return false
  }
  const responseText = xhr?.responseText?.trim?.() || ""
  if (responseText.startsWith("<")) {
    return true
  }
  return contentType.includes("text/html") || contentType.includes("application/xhtml+xml") || contentType.includes("text/plain")
}

const getRegisterFormRoot = (element) => {
  if (!element) {
    return null
  }
  if (element.matches?.('[x-data="registerForm"]')) {
    return element
  }
  return element.querySelector?.('[x-data="registerForm"]') || null
}

const clearRegisterFormTimers = (element) => {
  const root = getRegisterFormRoot(element)
  const state = root ? registerFormState.get(root) : null
  if (!state) {
    return
  }
  if (state.cooldownTimer) {
    clearInterval(state.cooldownTimer)
    state.cooldownTimer = null
  }
  if (state.verifiedTimer) {
    clearInterval(state.verifiedTimer)
    state.verifiedTimer = null
  }
  registerFormState.delete(root)
}

const bootApp = () => {
  const alpine = window.Alpine
  if (!alpine) {
    throw new Error("Alpine CSP bundle is not loaded")
  }

  window.Alpine = alpine

  document.addEventListener("alpine:init", () => {
    alpine.data("registerForm", () => ({
      verified: false,
      otpSent: false,
      sendingOtp: false,
      mobile: "",
      mobileTaken: false,
      mobileValid: false,
      submitting: false,
      verificationExpired: false,
      cooldownRemaining: 0,
      cooldownTimer: null,
      verifiedRemaining: 0,
      verifiedTimer: null,
      init() {
        registerFormState.set(this.$el, this)
        this.verified = this.$el.dataset.mobileVerified === "true"
        this.otpSent = this.verified
        this.verifiedRemaining = Number(this.$el.dataset.mobileVerifiedTtl || 0)
        if (this.verified && this.verifiedRemaining > 0) {
          this.startVerifiedTimer(this.verifiedRemaining)
        }
      },
      markMobileVerified(seconds) {
        this.verified = true
        this.otpSent = true
        this.verificationExpired = false
        this.startVerifiedTimer(seconds)
      },
      markOtpSent() {
        this.otpSent = true
        this.verificationExpired = false
      },
      resetMobileAvailability() {
        this.mobileTaken = false
        this.mobileValid = false
      },
      updateMobileAvailability(detail) {
        this.mobileTaken = !!detail?.exists
        this.mobileValid = !!detail?.valid
      },
      startCooldown(seconds) {
        this.cooldownRemaining = Math.max(0, Number(seconds) || 0)
        if (this.cooldownTimer) clearInterval(this.cooldownTimer)
        if (this.cooldownRemaining === 0) return
        this.cooldownTimer = setInterval(() => {
          if (this.cooldownRemaining > 0) this.cooldownRemaining -= 1
          if (this.cooldownRemaining === 0 && this.cooldownTimer) {
            clearInterval(this.cooldownTimer)
            this.cooldownTimer = null
          }
        }, 1000)
      },
      startVerifiedTimer(seconds) {
        this.verifiedRemaining = Math.max(0, Number(seconds) || 0)
        if (this.verifiedTimer) clearInterval(this.verifiedTimer)
        if (this.verifiedRemaining === 0) return
        this.verifiedTimer = setInterval(() => {
          if (this.verifiedRemaining > 0) this.verifiedRemaining -= 1
          if (this.verifiedRemaining === 0) {
            this.resetVerifiedState()
          }
        }, 1000)
      },
      formatVerifiedRemaining() {
        const minutes = String(Math.floor(this.verifiedRemaining / 60)).padStart(2, "0")
        const seconds = String(this.verifiedRemaining % 60).padStart(2, "0")
        return `${minutes}:${seconds}`
      },
      resetVerifiedState() {
        this.verified = false
        this.otpSent = false
        this.verifiedRemaining = 0
        if (this.verifiedTimer) {
          clearInterval(this.verifiedTimer)
          this.verifiedTimer = null
        }
        this.verificationExpired = true
      },
      formatCooldown() {
        const minutes = String(Math.floor(this.cooldownRemaining / 60)).padStart(2, "0")
        const seconds = String(this.cooldownRemaining % 60).padStart(2, "0")
        return `${minutes}:${seconds}`
      },
      isMobileFormatValid() {
        return /^\+[1-9]\d{7,14}$/.test(this.mobile.trim())
      },
      startSendingOtp() {
        this.sendingOtp = true
      },
      stopSendingOtp() {
        this.sendingOtp = false
      },
      startSubmitting() {
        this.submitting = true
      },
      stopSubmitting() {
        this.submitting = false
      },
    }))

    alpine.data("settingsPage", () => ({
      theme: "litestar",
      init() {
        this.theme = this.$el.dataset.theme || "litestar"
      },
      applyTheme() {
        document.documentElement.setAttribute("data-theme", this.theme)
      },
    }))

    alpine.data("collapsible", () => ({
      open: false,
      toggle() {
        this.open = !this.open
      },
      label() {
        return this.open ? "Hide" : "Show"
      },
    }))

    alpine.data("htmxForm", () => ({
      loading: false,
      startLoading() {
        this.loading = true
      },
      stopLoading() {
        this.loading = false
      },
    }))

    alpine.data("modalDialog", () => ({
      open: false,
      init() {
        this.open = this.$el.dataset.open === "true"
      },
      close() {
        this.open = false
      },
      show() {
        this.open = true
      },
    }))

    alpine.store("auth", {
      user: null,
      isAuthenticated: false,
      setUser(user) {
        this.user = user
        this.isAuthenticated = Boolean(user)
      },
      clear() {
        this.user = null
        this.isAuthenticated = false
      },
    })

    alpine.store("ui", {
      sidebarOpen: false,
      compactTables: false,
      toggleSidebar() {
        this.sidebarOpen = !this.sidebarOpen
      },
    })
  })

  registerHtmxExtension()
  document.body.addEventListener("htmx:configRequest", (event) => {
    const verb = event.detail?.verb?.toUpperCase()
    if (!verb || !unsafeVerbs.has(verb)) {
      return
    }
    const token = readCsrfToken()
    if (!token) {
      return
    }
    if (!event.detail.headers) {
      event.detail.headers = {}
    }
    event.detail.headers[csrfHeaderName] = token
  })
  document.body.addEventListener("htmx:afterRequest", (event) => {
    if (!event.detail?.successful) {
      return
    }
    const source = event.detail?.elt ?? event.target
    if (!(source instanceof HTMLFormElement)) {
      return
    }
    if (source.hasAttribute("data-htmx-reset-on-success")) {
      source.reset()
    }
  })
  document.body.addEventListener("htmx:beforeSwap", (event) => {
    const status = event.detail.xhr?.status
    if (!swappableClientErrors.has(status) || !isSwappableClientResponse(event.detail.xhr)) {
      return
    }
    // Allow HTMX to swap content for 4xx responses so error partials render in the target
    event.detail.shouldSwap = true
    event.detail.isError = false
  })
  document.body.addEventListener("htmx:responseError", (event) => {
    const status = event.detail.xhr?.status
    if (status !== 403) {
      return
    }
    const responseText = event.detail.xhr?.responseText ?? ""
    if (!responseText.toLowerCase().includes("csrf")) {
      const contentType = event.detail.xhr?.getResponseHeader("content-type") ?? ""
      let message = "You do not have permission to perform this action."
      if (contentType.includes("application/json")) {
        try {
          const payload = JSON.parse(responseText)
          message = payload.detail || payload.message || message
        } catch {
          message = message
        }
      } else if (responseText && !responseText.includes("<")) {
        message = responseText
      }
      showToast(message, "error")
      return
    }
    showToast(csrfErrorMessage, "error", 7000)
  })
  document.body.addEventListener("htmx:beforeCleanupElement", (event) => {
    clearRegisterFormTimers(event.detail?.elt)
  })
  document.body.addEventListener("htmx:historyCacheMiss", (event) => {
    const restorePath = event.detail?.path
    if (typeof restorePath === "string" && restorePath.length > 0) {
      window.location.assign(restorePath)
      return
    }
    window.location.reload()
  })
  document.body.addEventListener("click", (event) => {
    const action = event.target?.closest?.("[data-ui-action]")
    if (!action) {
      return
    }
    switch (action.getAttribute("data-ui-action")) {
      case "reload":
        window.location.reload()
        break
      case "back":
        window.history.back()
        break
      default:
        break
    }
  })

  if (isIOS || isFirefoxIOS) {
    // iOS browsers can fail to restore HTMX snapshots on browser back/forward.
    // Force a full reload of the active history entry for consistency.
    window.addEventListener("popstate", () => {
      window.location.reload()
    })
  }
  window.addEventListener("pagehide", () => {
    clearRegisterFormTimers(document.body)
  })
  if (typeof htmx.onLoad === "function") {
    htmx.onLoad((content) => {
      if (window.Alpine?.initTree) {
        window.Alpine.initTree(content)
      }
    })
  }
  htmx.process(document.body)
  alpine.start()
}

bootApp()
