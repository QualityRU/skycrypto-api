from utils.db_sessions import session_scope


def ban_ips():
    with session_scope() as session:
        items = session.execute(
            """
                SELECT ip
                FROM deal d
                WHERE created_at > now() - INTERVAL '90 minutes' AND state = 'deleted' AND ip is not null
                GROUP BY ip
                HAVING count(*) > 30
            """
        ).fetchall()
        for ip, in items:
            is_exists_success = session.execute(
                """
                    SELECT EXISTS(
                        SELECT 1
                        FROM deal d
                        WHERE created_at > now() - INTERVAL '2 hours' AND state = 'closed' AND ip = :ip
                    )
                """,
                {'ip': ip}
            ).scalar()
            if not is_exists_success:
                is_ip_exists = session.execute(
                    'SELECT EXISTS(SELECT 1 FROM baned_ip WHERE ip = :ip)',
                    {'ip': ip}
                ).scalar()
                if not is_ip_exists:
                    session.execute('INSERT INTO baned_ip (ip) VALUES (:ip)', {'ip': ip})

