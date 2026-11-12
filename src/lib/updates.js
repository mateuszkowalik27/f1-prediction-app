// Samoczynne aktualizacje aplikacji. `register` to registerSW z vite-plugin-pwa (w trybie autoUpdate sam
// przeładowuje stronę, gdy nowa wersja przejmie kontrolę). Tu dbamy o to, żeby nowa wersja została znaleziona:
// telefon trzyma aplikację w pamięci tygodniami, więc bez tego nowości nie pojawiłyby się bez ponownej instalacji.
export function setupUpdates(register, doc = document, intervalMs = 30 * 60 * 1000) {
  register({
    immediate: true,
    onRegisteredSW(_swUrl, registration) {
      if (!registration) return
      const check = () => registration.update().catch(() => {}) // bez internetu: po prostu spróbujemy później
      doc.addEventListener('visibilitychange', () => {
        if (doc.visibilityState === 'visible') check() // aplikacja wraca na pierwszy plan
      })
      setInterval(check, intervalMs) // i okresowo, gdy zostaje otwarta
    },
  })
}
