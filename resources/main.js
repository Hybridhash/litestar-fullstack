import htmx from "htmx.org"
import { registerHtmxExtension } from "litestar-vite-plugin/helpers"
import Alpine from "alpinejs"

window.htmx = htmx
window.Alpine = Alpine

const csrfErrorMessage = "CSRF validation failed. Please refresh the page and try again."
const csrfCookieName = "XSRF-TOKEN"
const csrfHeaderName = "X-XSRF-TOKEN"
const unsafeVerbs = new Set(["POST", "PUT", "PATCH", "DELETE"])
const userAgent = window.navigator?.userAgent || ""
const isFirefoxIOS = /FxiOS/i.test(userAgent)
const isIOS = /iPhone|iPad|iPod/i.test(userAgent)

// Mobile browsers can evict HTMX history snapshots aggressively; forcing a
// reload on cache misses keeps browser back/forward navigation reliable.
htmx.config.refreshOnHistoryMiss = true
htmx.config.historyCacheSize = Math.max(htmx.config.historyCacheSize || 0, 20)

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

document.addEventListener("alpine:init", () => {
  Alpine.store("auth", {
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

  Alpine.store("ui", {
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
  window.alert(csrfErrorMessage)
})
document.body.addEventListener("htmx:historyCacheMiss", (event) => {
  const restorePath = event.detail?.path
  if (typeof restorePath === "string" && restorePath.length > 0) {
    window.location.assign(restorePath)
    return
  }
  window.location.reload()
})

if (isIOS || isFirefoxIOS) {
  // iOS browsers can fail to restore HTMX snapshots on browser back/forward.
  // Force a full reload of the active history entry for consistency.
  window.addEventListener("popstate", () => {
    window.location.reload()
  })
}
if (typeof htmx.onLoad === "function") {
  htmx.onLoad((content) => {
    if (window.Alpine?.initTree) {
      window.Alpine.initTree(content)
    }
  })
}
htmx.process(document.body)
Alpine.start()
