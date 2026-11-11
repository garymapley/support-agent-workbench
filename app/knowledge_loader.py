from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class KnowledgeChunk:
    text: str
    source: str
    title: str
    policy_type: str
    version: str
    effective_date: str
    is_active: bool
    chunk_index: int


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        raise ValueError("知识文档缺少 YAML 式元数据头。")

    _, raw_metadata, body = content.split("---", 2)
    metadata: dict[str, str] = {}
    for line in raw_metadata.strip().splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, body.strip()


def load_knowledge_chunks(knowledge_dir: Path) -> list[KnowledgeChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=100,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", "，", ""],
    )
    chunks: list[KnowledgeChunk] = []

    for path in sorted(knowledge_dir.glob("*.md")):
        metadata, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        required = {
            "title",
            "policy_type",
            "version",
            "effective_date",
            "is_active",
        }
        missing = required.difference(metadata)
        if missing:
            raise ValueError(f"{path.name} 缺少元数据: {sorted(missing)}")

        for index, text in enumerate(splitter.split_text(body)):
            chunks.append(
                KnowledgeChunk(
                    text=text,
                    source=path.name,
                    title=metadata["title"],
                    policy_type=metadata["policy_type"],
                    version=metadata["version"],
                    effective_date=metadata["effective_date"],
                    is_active=metadata["is_active"].lower() == "true",
                    chunk_index=index,
                )
            )

    return chunks
