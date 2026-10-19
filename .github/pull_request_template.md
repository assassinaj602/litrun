## Description
Briefly explain the intent, implementation, and impact of these changes.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Hardware support / New SoC profile
- [ ] Model registry update
- [ ] Performance / Governor optimization
- [ ] Documentation update

## Hardware Tested On
- [ ] Physical Raspberry Pi 5 (BCM2712)
- [ ] Physical Raspberry Pi 4 (BCM2711)
- [ ] Physical Orange Pi 5 / RK3588
- [ ] QEMU aarch64 emulation
- [ ] x86_64 host

## Checklist
- [ ] Pure C core compiles with zero warnings under `-Wall -Wextra -Werror -pedantic`
- [ ] C tests pass (`make test`)
- [ ] Python tests pass (`pytest`)
- [ ] Output of `litrun inspect` verified
- [ ] Documentation updated if relevant
