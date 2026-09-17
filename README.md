# Heizplan

Custom Integration für Home Assistant: Wochenpläne pro Raum, Ausnahmen, gemeinsame
Temperaturen für „Warm“ und „Nacht“ – bedienbar über eine einzige Dashboard-Karte.

## Funktionen

- **Wochenplan pro Raum**: Warm-Zeiträume pro Wochentag; außerhalb gilt „Nacht“.
- **Zwei Temperaturen für alle Räume**: Warm (Standard 23 °C) und Nacht (18 °C), in der Karte änderbar.
- **Ausnahmen** mit Zeitraum, Räumen, Modus und Notiz (z. B. Homeoffice, Urlaub, Besuch).
  Schnellaktionen in der Karte: „2 Std. warm“, „Heute kühl lassen“, „Zurück zum Plan“.
- **Plan pro Raum pausieren** (z. B. im Sommer).
- **Handverstellung bleibt**: Heizplan setzt das Thermostat nur beim Wechsel Warm ↔ Nacht.
  Wer am Thermostat dreht, behält die Temperatur bis zum nächsten Wechsel.
- **Externer Temperatursensor (Aqara E1)**: Überträgt die Hygrometer-Temperatur (bei Änderung,
  spätestens alle 5 Minuten) und stellt `select.*_sensor` automatisch zurück auf `external`,
  wenn das Thermostat auf `internal` springt. Die Karte zeigt das 24 h lang als Hinweis an.

## Installation

**Über HACS (empfohlen)**: Dieses Repository als benutzerdefiniertes Repository
(Typ „Integration“) hinzufügen, „Heizplan“ installieren, Home Assistant neu starten.

**Manuell**: `custom_components/heizplan` nach `/config/custom_components/heizplan` kopieren
(z. B. über die Samba-Freigabe) und Home Assistant neu starten.

Danach: *Einstellungen → Geräte & Dienste → Integration hinzufügen → Heizplan*,
Thermostate wählen und pro Thermostat optional das Hygrometer.

## Karte

Die Karte wird von der Integration automatisch geladen (keine Ressource nötig):

```yaml
type: custom:heizplan-card
# optional:
title: Heizung        # "" blendet den Titel aus
rooms: [buro]         # nur bestimmte Räume anzeigen
```

## Entities

| Entity | Zweck |
|---|---|
| `sensor.heizplan_<raum>` | aktuelle Solltemperatur, Attribute: Modus, Quelle, nächster Wechsel, Sensor-Korrekturen |
| `switch.heizplan_<raum>_aktiv` | Plan für den Raum an/aus |
| `number.heizplan_warm_temperatur`, `number.heizplan_nacht_temperatur` | globale Temperaturen |

Dienste für eigene Automationen: `heizplan.add_exception`, `heizplan.delete_exception`.

## Entwicklung

```bash
python3 -m unittest tests/test_logic.py           # reine Logik, ohne HA
pip install pytest-homeassistant-custom-component
pytest                                            # inkl. Integrationstests
```
