# Rollladen

Custom Integration für Home Assistant zur Steuerung von Rollläden.

> **Status:** in Entwicklung, noch nicht nutzbar.

## Idee

- Die Integration ist die **Anlage** mit globalen Einstellungen (Automatik an/aus, Beschattung, Helligkeitsschwellen).
- Jeder **Rollladen** wird in der UI angelegt und bekommt ein eigenes Gerät mit Automatik-Schalter, Zeitfenstern und Status.
- Hardwareneutral: pro Rollladen eine beliebige `cover`-Entity mit Position. Optional ein Taster (`event`-Entity) für Auf/Zu und Stopp.
- Die Integration fährt hoch und runter nach Helligkeit oder Uhrzeit, beschattet, beachtet Fenstergriff und Tür (Aussperrschutz) und erkennt Handbetrieb.
- Keine `input_*`-Helfer und keine Automationen nötig. Zustände wie „letzte Fahrt“ hält die Integration selbst.

## Installation

Über den Marketplace als benutzerdefiniertes Repository:

1. Marketplace → ⋮ → *Benutzerdefinierte Repositories*
2. URL dieses Repos eintragen, Kategorie *Integration*
3. „Rollladen“ installieren, Home Assistant neu starten
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Rollladen*

## Lizenz

MIT
