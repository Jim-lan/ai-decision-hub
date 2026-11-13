"""PostgreSQL adapter for canonical workspace persistence."""

from app.ports import RepositoryNotFound
from app.security import digest


class PostgresConversationRepository:
    def __init__(self, connection):
        self.connection = connection

    def create_project(self, owner_id, name):
        return self.connection.execute(
            "INSERT INTO projects (name, owner_id) VALUES (%s,%s) RETURNING *",
            (name, owner_id),
        ).fetchone()

    def list_projects(self, owner_id):
        return self.connection.execute(
            "SELECT * FROM projects WHERE owner_id=%s ORDER BY created_at, project_id",
            (owner_id,),
        ).fetchall()

    def get_project(self, project_id, owner_id):
        row = self.connection.execute(
            "SELECT * FROM projects WHERE project_id=%s AND owner_id=%s",
            (project_id, owner_id),
        ).fetchone()
        if not row:
            raise RepositoryNotFound
        return row

    def create_conversation(self, project_id, title):
        return self.connection.execute(
            "INSERT INTO conversations (project_id, title) VALUES (%s,%s) RETURNING *",
            (project_id, title),
        ).fetchone()

    def list_conversations(self, project_id):
        return self.connection.execute(
            "SELECT * FROM conversations WHERE project_id=%s ORDER BY created_at, conversation_id",
            (project_id,),
        ).fetchall()

    def get_conversation(self, conversation_id, owner_id, *, lock=False):
        query = """SELECT c.* FROM conversations c JOIN projects p USING (project_id)
                   WHERE c.conversation_id=%s AND p.owner_id=%s"""
        if lock:
            query += " FOR UPDATE OF c"
        row = self.connection.execute(query, (conversation_id, owner_id)).fetchone()
        if not row:
            raise RepositoryNotFound
        return row

    def append_message(self, conversation_id, content):
        # The caller holds the conversation row lock until commit.
        return self.connection.execute("""
            INSERT INTO messages (conversation_id, sequence, role, content, source_hash)
            SELECT %s, COALESCE(MAX(sequence),0)+1, 'user', %s, %s
            FROM messages WHERE conversation_id=%s RETURNING *
        """, (conversation_id, content, digest(content), conversation_id)).fetchone()

    def list_messages(self, conversation_id, after_sequence, limit):
        return self.connection.execute("""
            SELECT * FROM messages WHERE conversation_id=%s AND sequence>%s
            ORDER BY sequence LIMIT %s
        """, (conversation_id, after_sequence, limit)).fetchall()

    def has_search_anchor(self, project_id, resource_id, created_at, query):
        return bool(self.connection.execute("""
            SELECT 1 FROM messages m JOIN conversations c USING (conversation_id)
            WHERE c.project_id=%s AND m.message_id=%s AND m.created_at=%s
              AND strpos(lower(m.content), lower(%s)) > 0
        """, (project_id, resource_id, created_at, query)).fetchone())

    def search_messages(
        self, project_id, query, after_created, after_kind, after_resource, limit,
    ):
        return self.connection.execute("""
            SELECT %s AS project_id, m.conversation_id, 'message' AS kind,
                   m.message_id AS resource_id, r.run_id, m.content, m.created_at
            FROM messages m
            JOIN conversations c USING (conversation_id)
            LEFT JOIN runs r USING (message_id)
            WHERE c.project_id=%s AND strpos(lower(m.content), lower(%s)) > 0
              AND (m.created_at, 'message'::text, m.message_id) > (%s, %s, %s)
            ORDER BY m.created_at, kind, m.message_id
            LIMIT %s
        """, (
            project_id, project_id, query, after_created, after_kind, after_resource, limit,
        )).fetchall()
