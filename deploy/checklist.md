# Лабораторная работа №2 — Чек-лист проверки на защите

Инструкция для демонстрации преподавателю выполнения всех сценариев проверки.

---

## 1. Перезагрузка обеих машин и проверка автоматического запуска

**Цель:** Доказать, что службы настроены на автозапуск через `systemctl enable` и поднимаются сами после ребута ОС.

1. Перезагрузите обе машины:
   ```bash
   # На db-server:
   sudo reboot

   # На app-server:
   sudo reboot
   ```
2. После загрузки машин подключитесь по SSH и проверьте статусы:
   ```bash
   # На db-server (проверка PostgreSQL):
   sudo systemctl status postgresql

   # На app-server (проверка службы приложения):
   sudo systemctl status cityduma
   ```
   *Ожидаемый статус:* `Active: active (running)` на обеих машинах.
3. Проверьте отклик приложения с хоста или сервера:
   ```bash
   curl http://localhost:8000/health
   # или с хост-машины Windows в браузере: http://localhost:8000/health
   ```
   *Ожидаемый ответ:*
   ```json
   {"status":"ok","database":"ok","version":"0.1.0"}
   ```

---

## 2. Остановка БД и диагностика состояния приложения

**Цель:** Показать устойчивость и диагностику при отказе базы данных.

1. Остановите PostgreSQL на `db-server`:
   ```bash
   # На db-server:
   sudo systemctl stop postgresql
   ```
2. Проверьте состояние приложения на `app-server`:
   ```bash
   # На app-server:
   curl -i http://localhost:8000/health
   ```
   *Ожидаемый результат:*
   Приложение продолжает отвечать HTTP 200, но сообщает об ошибке соединения с БД:
   ```json
   {"status":"ok","database":"error: ...","version":"0.1.0"}
   ```
3. Посмотрите журнал ошибок в реальном времени:
   ```bash
   # На app-server:
   sudo journalctl -u cityduma -f
   ```
4. Восстановите работу БД:
   ```bash
   # На db-server:
   sudo systemctl start postgresql
   ```
5. Убедитесь, что приложение снова работает штатно:
   ```bash
   curl http://localhost:8000/health
   # {"status":"ok","database":"ok","version":"0.1.0"}
   ```

---

## 3. Поиск процесса, порта и журналов средствами Linux

**Цель:** Продемонстрировать владение базовыми утилитами Linux для инспекции процессов, сети и логов.

1. **Поиск процесса:**
   ```bash
   ps aux | grep uvicorn
   ```
   *Что показать:* Процесс запущен от пользователя **`duma-app`** (требование: не запускать от `root`).
2. **Проверка открытых сетевых портов:**
   ```bash
   ss -tulpn | grep 8000
   # или
   sudo lsof -i :8000
   ```
   *Что показать:* Порт `0.0.0.0:8000` слушает процесс `uvicorn`.
3. **Просмотр журналов службы:**
   ```bash
   # Последние 30 строк журнала:
   sudo journalctl -u cityduma -n 30 --no-pager

   # Журнал в реальном времени (tail -f):
   sudo journalctl -u cityduma -f
   ```

---

## 4. Изменение одного параметра службы с последующим восстановлением

**Цель:** Показать цикл изменения конфигурации systemd (`daemon-reload`, `restart`).

1. Откройте файл службы на `app-server`:
   ```bash
   sudo nano /etc/systemd/system/cityduma.service
   ```
2. Измените порт в строке `ExecStart` с `8000` на `8080`:
   ```ini
   ExecStart=/opt/cityduma/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
   ```
3. Примените изменения:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart cityduma
   ```
4. Убедитесь, что служба слушает новый порт:
   ```bash
   ss -tulpn | grep 8080
   curl http://localhost:8080/health
   ```
5. Верните порт `8000` обратно:
   ```bash
   sudo sed -i 's/--port 8080/--port 8000/' /etc/systemd/system/cityduma.service
   sudo systemctl daemon-reload
   sudo systemctl restart cityduma
   ss -tulpn | grep 8000
   ```

---

## 5. Проверка сетевой недоступности БД с постороннего узла

**Цель:** Доказать, что база данных изолирована правилами межсетевого экрана (UFW) и доступна **только** серверу приложений.

1. **Проверка с постороннего узла (с хост-машины Windows):**
   В PowerShell на хосте выполните:
   ```powershell
   Test-NetConnection -ComputerName 172.27.206.20 -Port 5432
   ```
   *Ожидаемый результат:*
   `TcpTestSucceeded : False` (пакеты отбрасываются UFW, порт закрыт).
2. **Проверка с сервера приложений (172.27.206.10):**
   На `app-server` выполните:
   ```bash
   nc -zv 172.27.206.20 5432
   ```
   *Ожидаемый результат:*
   `Connection to 172.27.206.20 5432 port [tcp/postgresql] succeeded!`
3. **Демонстрация правил UFW на `db-server`:**
   ```bash
   # На db-server:
   sudo ufw status verbose
   ```
   *Что показать:*
   ```text
   To                         Action      From
   --                         ------      ----
   22/tcp                     ALLOW IN    Anywhere
   5432/tcp                   ALLOW IN    172.27.206.10
   ```
