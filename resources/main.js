import htmx from "htmx.org"
import { registerHtmxExtension } from "litestar-vite-plugin/helpers"
import Alpine from "alpinejs"

window.htmx = htmx
window.Alpine = Alpine
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
if (typeof htmx.onLoad === "function") {
  htmx.onLoad((content) => {
    if (window.Alpine?.initTree) {
      window.Alpine.initTree(content)
    }
  })
}
htmx.process(document.body)
Alpine.start()
