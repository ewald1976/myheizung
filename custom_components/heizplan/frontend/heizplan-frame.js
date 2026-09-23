/* Native iframe card bridge: no Lovelace custom-card registration is needed. */
(() => {
  const card = document.querySelector("heizplan-card-content");
  const params = new URLSearchParams(location.search);
  const config = {};
  if (params.has("title")) config.title = params.get("title");
  const rooms = params.getAll("room").filter(Boolean);
  if (rooms.length) config.rooms = rooms;
  const presets = params.get("presets");
  if (presets) config.presets = presets.split(",").map(Number).filter(Number.isFinite);
  customElements.whenDefined("heizplan-card-content").then(() => {
    customElements.upgrade(card);
    card.setConfig(config);
    sync();
  });

  const colors = [
    "--primary-text-color", "--secondary-text-color", "--card-background-color",
    "--primary-color", "--text-primary-color", "--secondary-background-color",
    "--divider-color", "--error-color", "--warning-color",
  ];
  let lastHass;
  function sync() {
    try {
      const parentApp = window.parent.document.querySelector("home-assistant");
      const hass = parentApp?.hass;
      if (hass && hass !== lastHass) {
        lastHass = hass;
        card.hass = hass;
      }
      if (parentApp) {
        const style = window.parent.getComputedStyle(parentApp);
        for (const name of colors) {
          const value = style.getPropertyValue(name);
          if (value) document.documentElement.style.setProperty(name, value);
        }
      }
    } catch (err) {
      document.body.textContent = `Heizplan kann Home Assistant nicht erreichen: ${err.message}`;
      return;
    }
    setTimeout(sync, 1000);
  }
})();
