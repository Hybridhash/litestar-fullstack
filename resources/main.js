import htmx from "htmx.org"
import { registerHtmxExtension } from "litestar-vite-plugin/helpers"
import Alpine from "alpinejs"

window.htmx = htmx
window.Alpine = Alpine

const csrfCookieName = "XSRF-TOKEN"
const csrfHeaderName = "X-XSRF-TOKEN"
const csrfUnsafeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"])
const csrfErrorMessage = "CSRF validation failed. Please refresh the page and try again."

const getCsrfTokenFromCookie = () => {
  const tokenPair = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${csrfCookieName}=`))
  if (!tokenPair) {
    return ""
  }
  return decodeURIComponent(tokenPair.split("=")[1] ?? "")
}

const shouldAttachCsrfToken = (method) => csrfUnsafeMethods.has(method.toUpperCase())
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
  if (!shouldAttachCsrfToken(event.detail.verb ?? "")) {
    return
  }
  const token = getCsrfTokenFromCookie()
  if (token) {
    event.detail.headers[csrfHeaderName] = token
  }
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
