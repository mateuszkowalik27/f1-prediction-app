// Czyści zapamiętaną wersję aplikacji (service worker i pamięć podręczną) i ładuje ją od nowa.
export async function resetApp() {
  try {
    const registrations = (await navigator.serviceWorker?.getRegistrations?.()) ?? []
    await Promise.all(registrations.map((r) => r.unregister()))
    await Promise.all((await caches.keys()).map((key) => caches.delete(key)))
  } catch {
    // nawet gdy czyszczenie się nie uda, i tak próbujemy załadować stronę od nowa
  }
  location.reload()
}
