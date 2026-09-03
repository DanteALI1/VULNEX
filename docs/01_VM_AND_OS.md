# 01. ВМ и установка РЕД ОС 8

Документ для человека, который раньше не ставил Linux. Команды копируйте целиком.

## 1. Что такое ВМ и рекомендуемые параметры

Виртуальная машина (ВМ) — «компьютер внутри компьютера». На гипервизоре создаёте ВМ и в неё ставите РЕД ОС 8.

| Ресурс | Минимум | Рекомендуется |
|---|---|---|
| vCPU | 2 | 4 |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 40 ГБ | 80+ ГБ SSD |
| Сеть | 1 NIC | bridged / VLAN площадки |

## 2. Создание ВМ

### VMware ESXi (основной вариант)

1. Откройте Host Client / vSphere.  
2. Create / Register VM → Create a new virtual machine.  
3. Guest OS: Linux → Other Linux (64-bit) или Red Hat compatible.  
4. CPU/RAM/Disk — из таблицы выше.  
5. Network: VM Network (или нужный VLAN).  
6. CD/DVD: Datastore ISO → выберите ISO РЕД ОС 8.  
7. Finish → Power on.

### VirtualBox (лаборатория на ПК)

1. New → Name `vulndb`, Type Linux, Version Other Linux (64-bit).  
2. Memory 8192 MB, Create VDI, динамический диск 80 GB.  
3. Settings → Storage → Optical → Choose ISO РЕД ОС 8.  
4. Network → Bridged Adapter (чтобы открыть UI с других ПК) или NAT + проброс 443.  
5. Start.

### Hyper-V (кратко)

New Virtual Machine → Generation 2 → Memory 8192 → Network switch → VHDX 80GB → Install from ISO.

## 3. Скачивание ISO РЕД ОС 8

1. Откройте портал РЕД СОФТ / внутренний зеркальный репозиторий вашей организации.  
2. Скачайте ISO **РЕД ОС 8** (Workstation/Server — как принято у вас).  
3. Проверьте контрольную сумму, если она опубликована рядом с ISO.

## 4. Установка ОС

1. Загрузитесь с ISO. Язык: **Русский**.  
2. Разметка диска:  
   - для новичка допустима одна `/` + swap;  
   - рекомендуется: `/` (20ГБ), `/var` (20ГБ+), `/opt` (20ГБ+), swap ≥ RAM.  
3. Hostname: например `vulndb-01`.  
4. Задайте пароль `root` (запишите в сейф; в docs используйте `CHANGE_ME_ROOT`).  
5. Сеть:  
   - DHCP — если выдали автоматический IP;  
   - статический: IP / маска / шлюз / DNS (спросите у сетевиков).  
6. Дождитесь конца установки → перезагрузка → извлеките ISO.

## 5. Первый вход и обновления

Войдите как `root` в консоль ВМ.

```bash
dnf -y update
dnf -y install chrony
systemctl enable --now chronyd
timedatectl set-ntp true
hostnamectl set-hostname vulndb-01
```

Ожидаемый вывод `timedatectl`: NTP synchronized: yes (или близко к этому после минуты).

## 6. Пользователь с sudo и SSH с Windows

```bash
useradd -m -G wheel deploy
passwd deploy   # задайте CHANGE_ME_DEPLOY
```

С Windows: PuTTY / Windows Terminal:

```text
ssh deploy@IP_АДРЕС_ВМ
```

Если SSH не пускает — на сервере:

```bash
dnf -y install openssh-server
systemctl enable --now sshd
```

## 7. Проверка сети

```bash
ip a
ping -c 3 8.8.8.8
ping -c 3 ya.ru
```

Если ping по IP работает, а по имени нет — поправьте DNS в `/etc/resolv.conf` или NetworkManager.

## Чеклист «готово, если…»

- [ ] ВМ запущена, РЕД ОС 8 установлена  
- [ ] `dnf update` выполнен  
- [ ] Есть пользователь с `sudo`  
- [ ] SSH с вашего ПК работает  
- [ ] Дальше → [02_STACK_INSTALL.md](02_STACK_INSTALL.md)  
