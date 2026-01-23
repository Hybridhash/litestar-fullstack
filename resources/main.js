import htmx from "htmx.org"
import { registerHtmxExtension } from "litestar-vite-plugin/helpers"
import Alpine from "alpinejs"

window.htmx = htmx
window.Alpine = Alpine

const csrfErrorMessage = "CSRF validation failed. Please refresh the page and try again."
const csrfCookieName = "XSRF-TOKEN"
const csrfHeaderName = "X-XSRF-TOKEN"
const unsafeVerbs = new Set(["post", "put", "patch", "delete"])

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
  const verb = event.detail?.verb?.toLowerCase()
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
  if (event.detail.xhr?.status !== 403) {
    return
  }
  const responseText = event.detail.xhr?.responseText ?? ""
  if (!responseText.toLowerCase().includes("csrf")) {
    return
  }
  window.alert(csrfErrorMessage)
})
if (typeof htmx.onLoad === "function") {
  htmx.onLoad((content) => {
    if (window.Alpine?.initTree) {
      window.Alpine.initTree(content)
    }
  })
}
htmx.process(document.body)
Alpine.start()
