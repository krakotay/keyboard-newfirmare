# Rights and license boundaries

The project's independently authored patch, utilities, tests and instructions
are distributed under the [MIT license](LICENSE).

## Manufacturer firmware

`firmware/stock-full-isp.bin` and `firmware/patched-v2-full-isp.bin` contain
manufacturer firmware for the VGN V108 Wired Keyboard / SINOWEALTH controller.
All rights to the manufacturer firmware belong to the manufacturer and its
respective original copyright holders. The project claims no ownership of that
firmware. **Neither firmware binary is distributed under the MIT license.**

The MIT grant applies to our independently authored modification, tools and
description of the difference. It does not relicense the underlying manufacturer
code in the patched binary or grant additional rights to the original firmware.

## Manufacturer documentation

The two unchanged PDFs in `docs/datasheets/` are original SINOWEALTH manufacturer
documentation. Their copyright remains with SINOWEALTH; the project's MIT license
does not apply. Sources and checksums are listed in
[the datasheet index](docs/datasheets/README.md). No manufacturer website scripts,
download archives or extracted PDF text are included.

## Open-source dependencies and references

These are separate, unmodified Git submodules. Their own licenses and notices
continue to apply; they are not relicensed by the root MIT license.

| Path | Source and pinned revision | License |
|---|---|---|
| `tools/sinowealth-kb-tool` | [shihuihzh/sinowealth-kb-tool](https://github.com/shihuihzh/sinowealth-kb-tool/tree/f568bd4b7b56c2fc4e5899e3d24ca6106a940b6e) | MIT, copyright 2023 Karolis Stasaitis; retain its `LICENSE` |
| `references/smk` | [carlossless/smk](https://github.com/carlossless/smk/tree/69373bbb633bd1159f4541f486ff7506563a38ec) | GNU GPL v2; retain its `LICENSE` and source notices |

The SMK source is a reference, not part of the supplied manufacturer image or the
three-byte patch. The flash utility invokes the separate sinowealth-kb-tool
executable; it does not embed its source code.
