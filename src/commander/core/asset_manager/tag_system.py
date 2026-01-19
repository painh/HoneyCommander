"""Tag management system with aliases and inheritance."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .database import get_database


@dataclass
class Tag:
    """Represents a tag."""

    id: int
    name: str
    namespace: str = ""
    color: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "Tag":
        """Create Tag from database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            namespace=row["namespace"] or "",
            color=row["color"],
            created_at=row["created_at"],
        )

    @property
    def full_name(self) -> str:
        """Get full tag name with namespace."""
        if self.namespace:
            return f"{self.namespace}:{self.name}"
        return self.name

    def __str__(self) -> str:
        return self.full_name


class TagManager:
    """Manager for tag operations including aliases and inheritance."""

    _instance: Optional["TagManager"] = None

    def __new__(cls) -> "TagManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._db = get_database()
        self._initialized = True

    # === Tag Parsing ===

    @staticmethod
    def parse_tag_string(tag_str: str) -> tuple[str, str]:
        """Parse tag string into namespace and name.

        Args:
            tag_str: Tag string (e.g., "character:player" or "boss")

        Returns:
            Tuple of (namespace, name)
        """
        tag_str = tag_str.strip().lower()
        if ":" in tag_str:
            namespace, name = tag_str.split(":", 1)
            return namespace.strip(), name.strip()
        return "", tag_str

    # === Tag CRUD ===

    def create_tag(
        self,
        name: str,
        namespace: str = "",
        color: Optional[str] = None,
    ) -> Tag:
        """Create a new tag.

        Args:
            name: Tag name
            namespace: Tag namespace (e.g., "character", "type")
            color: Optional hex color

        Returns:
            Created Tag object
        """
        name = name.strip().lower()
        namespace = namespace.strip().lower()

        self._db.execute(
            """
            INSERT INTO tags (name, namespace, color)
            VALUES (?, ?, ?)
            """,
            (name, namespace, color),
        )
        self._db.commit()

        row = self._db.fetchone(
            "SELECT * FROM tags WHERE namespace = ? AND name = ?",
            (namespace, name),
        )
        return Tag.from_row(row)

    def get_or_create_tag(
        self,
        name: str,
        namespace: str = "",
        color: Optional[str] = None,
    ) -> Tag:
        """Get existing tag or create new one.

        Args:
            name: Tag name
            namespace: Tag namespace
            color: Optional hex color (only used for new tags)

        Returns:
            Tag object
        """
        name = name.strip().lower()
        namespace = namespace.strip().lower()

        row = self._db.fetchone(
            "SELECT * FROM tags WHERE namespace = ? AND name = ?",
            (namespace, name),
        )

        if row:
            return Tag.from_row(row)

        return self.create_tag(name, namespace, color)

    def get_or_create_from_string(self, tag_str: str) -> Tag:
        """Get or create tag from string like "namespace:name" or "name".

        Args:
            tag_str: Tag string

        Returns:
            Tag object
        """
        namespace, name = self.parse_tag_string(tag_str)
        return self.get_or_create_tag(name, namespace)

    def get_tag(self, tag_id: int) -> Optional[Tag]:
        """Get tag by ID."""
        row = self._db.fetchone("SELECT * FROM tags WHERE id = ?", (tag_id,))
        return Tag.from_row(row) if row else None

    def get_tag_by_name(self, name: str, namespace: str = "") -> Optional[Tag]:
        """Get tag by name and namespace."""
        name = name.strip().lower()
        namespace = namespace.strip().lower()

        row = self._db.fetchone(
            "SELECT * FROM tags WHERE namespace = ? AND name = ?",
            (namespace, name),
        )
        return Tag.from_row(row) if row else None

    def get_all_tags(self) -> list[Tag]:
        """Get all tags ordered by namespace and name."""
        rows = self._db.fetchall("SELECT * FROM tags ORDER BY namespace, name")
        return [Tag.from_row(row) for row in rows]

    def get_tags_by_namespace(self, namespace: str) -> list[Tag]:
        """Get all tags in a namespace."""
        rows = self._db.fetchall(
            "SELECT * FROM tags WHERE namespace = ? ORDER BY name",
            (namespace.strip().lower(),),
        )
        return [Tag.from_row(row) for row in rows]

    def get_namespaces(self) -> list[str]:
        """Get all unique namespaces."""
        rows = self._db.fetchall(
            "SELECT DISTINCT namespace FROM tags WHERE namespace != '' ORDER BY namespace"
        )
        return [row["namespace"] for row in rows]

    def search_tags(self, query: str, limit: int = 20) -> list[Tag]:
        """Search tags by name or namespace.

        Args:
            query: Search query (partial match)
            limit: Maximum results

        Returns:
            List of matching tags
        """
        query = f"%{query.strip().lower()}%"
        rows = self._db.fetchall(
            """
            SELECT * FROM tags
            WHERE name LIKE ? OR namespace LIKE ?
            ORDER BY namespace, name
            LIMIT ?
            """,
            (query, query, limit),
        )
        return [Tag.from_row(row) for row in rows]

    def update_tag(
        self,
        tag_id: int,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
        color: Optional[str] = None,
    ) -> None:
        """Update tag properties."""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name.strip().lower())

        if namespace is not None:
            updates.append("namespace = ?")
            params.append(namespace.strip().lower())

        if color is not None:
            updates.append("color = ?")
            params.append(color)

        if not updates:
            return

        params.append(tag_id)
        self._db.execute(
            f"UPDATE tags SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        self._db.commit()

    def delete_tag(self, tag_id: int) -> None:
        """Delete a tag (also removes from all assets)."""
        self._db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self._db.commit()

    def get_tag_usage_count(self, tag_id: int) -> int:
        """Get number of assets using this tag."""
        row = self._db.fetchone(
            "SELECT COUNT(*) as count FROM asset_tags WHERE tag_id = ?",
            (tag_id,),
        )
        return row["count"]

    # === Tag Relationships ===

    def add_sibling(self, tag_id: int, sibling_tag_id: int) -> None:
        """Add sibling (alias) relationship.

        When searching for tag_id, also match sibling_tag_id.
        """
        self._db.execute(
            """
            INSERT OR IGNORE INTO tag_relationships (tag_id, related_tag_id, relationship_type)
            VALUES (?, ?, 'sibling')
            """,
            (tag_id, sibling_tag_id),
        )
        # Make relationship bidirectional
        self._db.execute(
            """
            INSERT OR IGNORE INTO tag_relationships (tag_id, related_tag_id, relationship_type)
            VALUES (?, ?, 'sibling')
            """,
            (sibling_tag_id, tag_id),
        )
        self._db.commit()

    def add_parent(self, child_tag_id: int, parent_tag_id: int) -> None:
        """Add parent relationship.

        When child tag is added, parent tag is automatically implied.
        """
        self._db.execute(
            """
            INSERT OR IGNORE INTO tag_relationships (tag_id, related_tag_id, relationship_type)
            VALUES (?, ?, 'parent')
            """,
            (child_tag_id, parent_tag_id),
        )
        self._db.commit()

    def remove_relationship(
        self,
        tag_id: int,
        related_tag_id: int,
        relationship_type: str,
    ) -> None:
        """Remove a tag relationship."""
        self._db.execute(
            """
            DELETE FROM tag_relationships
            WHERE tag_id = ? AND related_tag_id = ? AND relationship_type = ?
            """,
            (tag_id, related_tag_id, relationship_type),
        )

        # For siblings, remove the reverse relationship too
        if relationship_type == "sibling":
            self._db.execute(
                """
                DELETE FROM tag_relationships
                WHERE tag_id = ? AND related_tag_id = ? AND relationship_type = ?
                """,
                (related_tag_id, tag_id, relationship_type),
            )

        self._db.commit()

    def get_siblings(self, tag_id: int) -> list[Tag]:
        """Get all sibling (alias) tags."""
        rows = self._db.fetchall(
            """
            SELECT t.* FROM tags t
            JOIN tag_relationships tr ON t.id = tr.related_tag_id
            WHERE tr.tag_id = ? AND tr.relationship_type = 'sibling'
            """,
            (tag_id,),
        )
        return [Tag.from_row(row) for row in rows]

    def get_parents(self, tag_id: int) -> list[Tag]:
        """Get all parent tags (direct parents only)."""
        rows = self._db.fetchall(
            """
            SELECT t.* FROM tags t
            JOIN tag_relationships tr ON t.id = tr.related_tag_id
            WHERE tr.tag_id = ? AND tr.relationship_type = 'parent'
            """,
            (tag_id,),
        )
        return [Tag.from_row(row) for row in rows]

    def get_all_parents(self, tag_id: int) -> list[Tag]:
        """Get all parent tags recursively (including grandparents)."""
        all_parents = []
        visited = set()
        to_visit = [tag_id]

        while to_visit:
            current_id = to_visit.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            parents = self.get_parents(current_id)
            for parent in parents:
                if parent.id not in visited:
                    all_parents.append(parent)
                    to_visit.append(parent.id)

        return all_parents

    def get_children(self, tag_id: int) -> list[Tag]:
        """Get all child tags (tags that have this as parent)."""
        rows = self._db.fetchall(
            """
            SELECT t.* FROM tags t
            JOIN tag_relationships tr ON t.id = tr.tag_id
            WHERE tr.related_tag_id = ? AND tr.relationship_type = 'parent'
            """,
            (tag_id,),
        )
        return [Tag.from_row(row) for row in rows]

    def resolve_canonical_tag(self, tag_id: int) -> Tag:
        """Resolve tag to its canonical form (following sibling chain).

        Returns the tag with the lowest ID among siblings.
        """
        tag = self.get_tag(tag_id)
        if tag is None:
            raise ValueError(f"Tag not found: {tag_id}")

        siblings = self.get_siblings(tag_id)
        if not siblings:
            return tag

        # Return the one with lowest ID (canonical)
        all_tags = [tag] + siblings
        return min(all_tags, key=lambda t: t.id)

    # === Library-specific tag operations ===

    def get_library_tags(self, library_id: int) -> list[Tag]:
        """Get all tags used in a library."""
        rows = self._db.fetchall(
            """
            SELECT DISTINCT t.* FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            JOIN assets a ON at.asset_id = a.id
            WHERE a.library_id = ?
            ORDER BY t.namespace, t.name
            """,
            (library_id,),
        )
        return [Tag.from_row(row) for row in rows]

    def get_library_tag_counts(self, library_id: int) -> dict[int, int]:
        """Get tag usage counts for a library.

        Returns:
            Dict mapping tag_id to usage count
        """
        rows = self._db.fetchall(
            """
            SELECT t.id, COUNT(at.asset_id) as count FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            JOIN assets a ON at.asset_id = a.id
            WHERE a.library_id = ?
            GROUP BY t.id
            """,
            (library_id,),
        )
        return {row["id"]: row["count"] for row in rows}


def get_tag_manager() -> TagManager:
    """Get the singleton tag manager instance."""
    return TagManager()
