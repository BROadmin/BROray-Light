# BROray-Light 3.5.10

BROray-Light — лёгкий менеджер Xray для роутеров Keenetic и Netcraze. Go-бинарник содержит WebUI с тремя страницами и использует учётные записи роутера. Xray устанавливается отдельно с Главной.

## Скачать Stable 3.5.10

| Архитектура пакетов Entware | Архив Linux | Размер архива |
| --- | --- | ---: |
| `aarch64-3.10` | [ARM64](https://github.com/BROadmin/BROray-Light/releases/download/v3.5.10/broray-light-3.5.10-linux-arm64.tar.gz) | 3 286 864 Б |
| `armv7-3.2` | [ARMv7](https://github.com/BROadmin/BROray-Light/releases/download/v3.5.10/broray-light-3.5.10-linux-armv7.tar.gz) | 3 434 990 Б |
| `mipsel-3.4` | [MIPSEL softfloat](https://github.com/BROadmin/BROray-Light/releases/download/v3.5.10/broray-light-3.5.10-linux-mipsel.tar.gz) | 3 235 499 Б |
| `mips-3.4` | [MIPS softfloat](https://github.com/BROadmin/BROray-Light/releases/download/v3.5.10/broray-light-3.5.10-linux-mips.tar.gz) | 3 249 536 Б |

Сверьте архитектуру командой `opkg print-architecture`. Для архива и извлечённого бинарника опубликованы отдельные контрольные суммы. [Релиз GitHub](https://github.com/BROadmin/BROray-Light/releases/tag/v3.5.10) · [SHA256SUMS](https://github.com/BROadmin/BROray-Light/releases/download/v3.5.10/SHA256SUMS) · [SHA256SUMS.binaries](https://github.com/BROadmin/BROray-Light/releases/download/v3.5.10/SHA256SUMS.binaries)

- [Установка и ручной переход с Light 1.x/2.0](docs/INSTALL-GO.md)
- [Руководство по WebUI, серверам и подпискам](docs/USER-GUIDE-GO.md)
- [Документация на сайте](https://docs.brovibe.cloud/broray-light/)
- [История версий](CHANGELOG.md) · [Проверки и ограничения](docs/VALIDATION-GO.md) · [Закреплённый донор](docs/UPSTREAM-GO.md)

При установке WebUI становится доступен на `http://LAN-IP:8080/` и, при зарегистрированном домене роутера, на `https://brolight.ДОМЕН-KEENDNS/`. На тестовом роутере проверена ARM64-сборка. Для ARMv7, MIPSEL и MIPS подтверждены сборки. Официальные MIPSEL/MIPS-архивы Xray 26.11.9 используют hardfloat. [Требования к ядру](docs/INSTALL-GO.md#совместимость-ядра-на-mips)

Переход со старого shell Light выполняется вручную с резервной копией ссылок, подписок и настроек. Последующие обновления Go-версии используют отдельный подписанный канал. Архивы содержат GPL-3.0 и лицензии компонентов. [Лицензия](LICENSE)
