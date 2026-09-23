/* Kleiner, sofort ladbarer Wrapper gegen HAs asynchrones Ressourcen-Race. */
(() => {

class HeizplanCardLoader extends HTMLElement {
  constructor() {
    super();
    this.style.display = "block";
    this._mount();
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
    if (this._content) this._content.setConfig(this._config);
  }

  set hass(hass) {
    this._hass = hass;
    if (this._content) this._content.hass = hass;
  }

  getCardSize() {
    return this._content?.getCardSize?.() || 8;
  }

  async _mount() {
    await customElements.whenDefined("heizplan-card-content");
    if (this._content) return;
    const content = document.createElement("heizplan-card-content");
    this._content = content;
    content.setConfig(this._config || {});
    if (this._hass) content.hass = this._hass;
    this.replaceChildren(content);
  }
}

if (!customElements.get("heizplan-card")) {
  customElements.define("heizplan-card", HeizplanCardLoader);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "heizplan-card",
    name: "Heizplan",
    description: "Wochenpläne, Ausnahmen und Temperaturen für die Heizung",
  });
}
})();
