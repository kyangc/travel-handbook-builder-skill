# Third-party notices

The MIT license in `LICENSE` applies to original files in this project. It does not relicense third-party software, specifications, data, trademarks, or other material. Each dependency remains under its own license.

The portable skill ZIP does not vendor the Python packages below. `scripts/setup_runtime.py` installs them into the skill-local `.venv` from the configured Python package index. If that environment is redistributed, retain the license files supplied in each installed package's `.dist-info` directory and follow the corresponding license terms.

Python itself and the `venv`/pip bootstrap tooling come from the user's Python installation and are outside this runtime dependency inventory.

## Observed runtime dependency snapshot

This table records the environment produced on 2026-09-20 with Python 3.12.1 from `jsonschema[format]==4.26.0` and `tzdata>=2024.1`. Transitive versions can change on a later install because they are not all pinned; regenerate and review this inventory for a release made from a different resolved environment.

| Package | Observed version | Relationship | License reported by installed metadata or license file | Upstream source |
|---|---:|---|---|---|
| jsonschema | 4.26.0 | direct, with `format` extra | MIT | [python-jsonschema/jsonschema](https://github.com/python-jsonschema/jsonschema) |
| attrs | 26.1.0 | jsonschema | MIT | [python-attrs/attrs](https://github.com/python-attrs/attrs) |
| jsonschema-specifications | 2025.9.1 | jsonschema | MIT | [python-jsonschema/jsonschema-specifications](https://github.com/python-jsonschema/jsonschema-specifications) |
| referencing | 0.37.0 | jsonschema and jsonschema-specifications | MIT | [python-jsonschema/referencing](https://github.com/python-jsonschema/referencing) |
| rpds-py | 2026.6.3 | jsonschema and referencing | MIT | [crate-py/rpds](https://github.com/crate-py/rpds) |
| typing-extensions | 4.16.0 | referencing on Python 3.12 | PSF-2.0 | [python/typing_extensions](https://github.com/python/typing_extensions) |
| fqdn | 1.5.1 | jsonschema `format` extra | MPL-2.0 | [ypcrts/fqdn](https://github.com/ypcrts/fqdn) |
| idna | 3.20 | jsonschema `format` extra | BSD-3-Clause | [kjd/idna](https://github.com/kjd/idna) |
| isoduration | 20.11.0 | jsonschema `format` extra | ISC | [bolsote/isoduration](https://github.com/bolsote/isoduration) |
| arrow | 1.4.0 | isoduration | Apache-2.0 | [arrow-py/arrow](https://github.com/arrow-py/arrow) |
| python-dateutil | 2.9.0.post0 | arrow | Apache-2.0 or BSD-3-Clause | [dateutil/dateutil](https://github.com/dateutil/dateutil) |
| six | 1.17.0 | python-dateutil and rfc3339-validator | MIT | [benjaminp/six](https://github.com/benjaminp/six) |
| jsonpointer | 3.1.1 | jsonschema `format` extra | BSD-3-Clause | [stefankoegl/python-json-pointer](https://github.com/stefankoegl/python-json-pointer) |
| rfc3339-validator | 0.1.4 | jsonschema `format` extra | MIT | [naimetti/rfc3339-validator](https://github.com/naimetti/rfc3339-validator) |
| rfc3987 | 1.3.8 | jsonschema `format` extra | GPL-3.0-or-later | [dgerber/rfc3987](https://github.com/dgerber/rfc3987) |
| uri-template | 1.3.0 | jsonschema `format` extra | MIT | [python-uri-template](https://gitlab.linss.com/open-source/python/uri-template) |
| webcolors | 25.10.0 | jsonschema `format` extra | BSD-3-Clause | [ubernostrum/webcolors](https://github.com/ubernostrum/webcolors) |
| tzdata | 2026.4 | direct fallback and arrow dependency | Apache-2.0 | [python/tzdata](https://github.com/python/tzdata) |

The `jsonschema` `format` extra is the reason `rfc3987` appears in this snapshot under GPL-3.0-or-later. It remains a separately installed dependency and is not covered by this project's MIT license. A release policy that excludes that dependency would require a separately tested dependency change; relabeling it is not an option.

`tzdata` packages the IANA time zone database as a fallback for systems without a usable system database. Its installed distribution includes its own license files; this project does not claim ownership of that data.

The observed metadata is also available from the relevant package release pages on [PyPI](https://pypi.org/). Package and license names above are attribution facts, not endorsements by their maintainers.

## Bundled Web dependency: Leaflet 1.9.4

The portable Web assets include Leaflet 1.9.4. Its complete upstream license follows; map-data attribution is separate from this software license.

Source: https://github.com/Leaflet/Leaflet/blob/v1.9.4/LICENSE

```text
BSD 2-Clause License

Copyright (c) 2010-2023, Volodymyr Agafonkin
Copyright (c) 2010-2011, CloudMade
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```


## Open-Meteo weather service

The optional browser weather adapter uses the Open-Meteo free API for non-commercial use. Weather data attribution: [Open-Meteo](https://open-meteo.com/) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). An information button immediately after each weather location title reveals provider and licence links, accessible by hover, keyboard focus or tap. The popover notes that displayed numbers are rounded. There is no separate page-bottom source section. Attribution requirements: <https://open-meteo.com/en/licence>. No weather response is bundled as canonical content; only explicit manual offline saving stores a runtime forecast snapshot. Service conditions and privacy: <https://open-meteo.com/en/terms>. Commercial use requires a separately reviewed provider arrangement; no API credential is included in this package.


## Bundled Web dependency: Lucide React

Weather cards use the installed Lucide React icons. The complete upstream license follows, including the notice for Feather-derived icons. Source: https://github.com/lucide-icons/lucide

```text
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

---

The following Lucide icons are derived from the Feather project:

airplay, alert-circle, alert-octagon, alert-triangle, aperture, arrow-down-circle, arrow-down-left, arrow-down-right, arrow-down, arrow-left-circle, arrow-left, arrow-right-circle, arrow-right, arrow-up-circle, arrow-up-left, arrow-up-right, arrow-up, at-sign, calendar, cast, check, chevron-down, chevron-left, chevron-right, chevron-up, chevrons-down, chevrons-left, chevrons-right, chevrons-up, circle, clipboard, clock, code, columns, command, compass, corner-down-left, corner-down-right, corner-left-down, corner-left-up, corner-right-down, corner-right-up, corner-up-left, corner-up-right, crosshair, database, divide-circle, divide-square, dollar-sign, download, external-link, feather, frown, hash, headphones, help-circle, info, italic, key, layout, life-buoy, link-2, link, loader, lock, log-in, log-out, maximize, meh, minimize, minimize-2, minus-circle, minus-square, minus, monitor, moon, more-horizontal, more-vertical, move, music, navigation-2, navigation, octagon, pause-circle, percent, plus-circle, plus-square, plus, power, radio, rss, search, server, share, shopping-bag, sidebar, smartphone, smile, square, table-2, tablet, target, terminal, trash-2, trash, triangle, tv, type, upload, x-circle, x-octagon, x-square, x, zoom-in, zoom-out

The MIT License (MIT) (for the icons listed above)

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
