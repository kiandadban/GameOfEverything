---
id: database_expose
description: Configures a database server to listen on all network interfaces (0.0.0.0) instead of localhost only, exposing it to direct remote connections from any host.
required_vars: [db_type]
requires_service_by:
  var: db_type
  map:
    mysql: mysql
    mariadb: mysql
    postgres: postgres
    postgresql: postgres
    redis: redis
    mongodb: mongodb
    mongo: mongodb
---
# Atom: Database Network Exposure
A database server is configured to accept connections from any IP address rather than being locked to localhost. Combined with weak or absent authentication, this allows direct remote access to the database.

> **The database server is provided by the platform.** The planner pins which engine
> this is via `config.db_type`, and the matching service recipe (resolved through
> `requires_service_by`) installs the correct package for the target distro and starts
> it. The entity script MUST NOT install or start the database. It applies only the
> vulnerability: changing the bind/listen address to all interfaces and reloading. Use
> the `db_type` the planner chose — do not switch engines.

### Logic Requirements:
1. Modify the bind-address / listen configuration of the pinned `<db_type>` to `0.0.0.0` or equivalent.
2. Reload (not reinstall) the service so the new bind address takes effect, without a distro init system (no `systemctl`).

### Common Patterns:

**MySQL / MariaDB:**
```bash
# Point the daemon at all interfaces (version-agnostic: write a drop-in conf)
echo -e "[mysqld]\nbind-address = 0.0.0.0" > /etc/mysql/conf.d/expose.cnf
# Grant remote access to root, then reload privileges (service already running)
mysql -e "CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'root'; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;"
```

**PostgreSQL:**
```bash
# listen on all interfaces (version-agnostic path via find)
PG_CONF=$(find /etc/postgresql -name postgresql.conf 2>/dev/null | head -1)
sed -i "s/^#\?listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"
PG_HBA=$(find /etc/postgresql -name pg_hba.conf 2>/dev/null | head -1)
echo "host all all 0.0.0.0/0 md5" >> "$PG_HBA"
# reload (not restart) over the local socket
su -c "psql -c \"SELECT pg_reload_conf();\"" postgres
```

**Redis:**
```bash
# See redis_disable_auth atom for the full misconfig; the recipe owns install/start.
sed -i 's/^bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
```

### Testing Guidance:
1. Verify the service is listening on `0.0.0.0` or `*`:
   - MySQL: `ss -tlnp | grep 3306` — should show `0.0.0.0:3306`
   - PostgreSQL: `ss -tlnp | grep 5432` — should show `0.0.0.0:5432`
2. From outside the container (attacker context), connect to `<container_ip>:<port>` using the appropriate client.
3. Verify data is accessible: run a query or list databases.

### Synthesis Guidance:
Install/start/bind of the engine is owned by the service recipe for the pinned `db_type`; the entity must not duplicate it. The atom applies only the bind-address change (+ a remote grant for MySQL) and a reload. Always resolve the exact config path for the installed version (e.g. PostgreSQL paths vary: `/etc/postgresql/14/main/` vs `/etc/postgresql/16/main/`) with a glob/`find` rather than hardcoding. Combine with `weak_service_password` or auth-disabling atoms to make the exposure directly exploitable.
