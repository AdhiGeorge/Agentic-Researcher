from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import uuid
from typing import List, Dict, Optional
import subprocess
import os
import socket
from src.core.config import Config
import re

class KnowledgeBase:
    def __init__(self, qdrant_url: str = 'http://localhost:6333', collection_name: str = 'research_knowledge'):
        self.qdrant_client = QdrantClient(url=qdrant_url)
        self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
        self.collection_name = collection_name
        self.chunk_size = 800  # tokens/chars, adjust for your embedding model
        # self._ensure_qdrant_running()  # DISABLED: not compatible with URL-based config
    
    def _ensure_qdrant_running(self):
        """Ensure Qdrant is running locally using the binary from config.yaml"""
        config = Config()
        binary_path = config.get('qdrant.binary_path', './qdrant/qdrant.exe')
        # Check if Qdrant is running
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((self.host, self.port))
        sock.close()
        if result != 0:
            print(f"Starting Qdrant from {binary_path}...")
            subprocess.Popen([binary_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    def _ensure_collection(self):
        """Ensure the collection exists with proper configuration"""
        collections = self.client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if self.collection_name not in collection_names:
            # Create collection with vector size 384 (all-MiniLM-L6-v2)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
    
    def _chunk_text(self, text: str, chunk_size: int = None) -> List[str]:
        """
        Chunk text into pieces of at most chunk_size (default: self.chunk_size),
        ending at the last period, and overlap the last complete sentence from the previous chunk.
        No data is lost.
        """
        if chunk_size is None:
            chunk_size = self.chunk_size
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ''
        last_sentence = ''
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                if current_chunk:
                    current_chunk += ' '
                current_chunk += sentence
                last_sentence = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Overlap: start next chunk with last complete sentence
                current_chunk = last_sentence + ' ' + sentence
                last_sentence = sentence
        if current_chunk:
            chunks.append(current_chunk.strip())
        # Remove duplicates due to overlap
        deduped_chunks = []
        for i, chunk in enumerate(chunks):
            if i == 0 or chunk != chunks[i-1]:
                deduped_chunks.append(chunk)
        return deduped_chunks

    def add_knowledge(self, text: str, metadata: Dict = None) -> List[str]:
        """Add a piece of knowledge to the vector database, chunking if needed. Returns list of point IDs."""
        chunk_size = self.chunk_size
        chunks = self._chunk_text(text, chunk_size)
        point_ids = []
        for i, chunk in enumerate(chunks):
            embedding = self.sentence_transformer.encode(chunk).tolist()
            point_id = str(uuid.uuid4())
            payload = {
                "text": chunk,
                "metadata": metadata or {},
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            point_ids.append(point_id)
        return point_ids
    
    def search_knowledge(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for relevant knowledge based on a query"""
        # Generate query embedding
        query_embedding = self.sentence_transformer.encode(query).tolist()
        
        # Search in collection
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit
        )
        
        # Format results
        results = []
        for point in search_result:
            results.append({
                "id": point.id,
                "text": point.payload.get("text", ""),
                "metadata": point.payload.get("metadata", {}),
                "score": point.score
            })
        
        return results
    
    def add_research_result(self, query: str, answer: str, sources: List[str] = None, session_id: int = None):
        """Add a complete research result to the knowledge base"""
        metadata = {
            "type": "research_result",
            "query": query,
            "sources": sources or [],
            "session_id": session_id
        }
        
        return self.add_knowledge(answer, metadata)
    
    def get_relevant_context(self, query: str, limit: int = 3) -> str:
        """Get relevant context from previous research for a query"""
        results = self.search_knowledge(query, limit)
        
        if not results:
            return ""
        
        context_parts = []
        for result in results:
            context_parts.append(f"Previous research: {result['text']}")
        
        return "\n\n".join(context_parts)
    
    def delete_knowledge(self, point_id: str):
        """Delete a piece of knowledge from the database"""
        self.qdrant_client.delete(
            collection_name=self.collection_name,
            points_selector=[point_id]
        )

    def store_research(self, research_data: str, query: str, session_id: str):
        """Store research data with query and session_id."""
        embedding = self.sentence_transformer.encode(research_data)
        point = {
            "id": str(uuid.uuid4()),
            "vector": embedding.tolist(),
            "payload": {"query": query, "session_id": session_id, "data": research_data}
        }
        self.qdrant_client.upsert(collection_name=self.collection_name, points=[point])

    def retrieve_research(self, query: str, session_id: str = None, limit: int = 5) -> list:
        """Retrieve research by query and/or session_id using semantic search."""
        query_embedding = self.sentence_transformer.encode(query)
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding.tolist(),
            limit=limit,
            query_filter={"must": [{"key": "session_id", "match": {"value": session_id}}]} if session_id else None
        )
        return [hit.payload["data"] for hit in search_result]

    def retrieve_code(self, session_id: str) -> str:
        """Retrieve code by session_id."""
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=self.sentence_transformer.encode("Python code").tolist(),
            limit=1,
            query_filter={"must": [{"key": "session_id", "match": {"value": session_id}}]}
        )
        return search_result[0].payload["data"] if search_result else ""

    def retrieve_report(self, session_id: str) -> str:
        """Retrieve report by session_id."""
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=self.sentence_transformer.encode("report").tolist(),
            limit=1,
            query_filter={"must": [{"key": "session_id", "match": {"value": session_id}}]}
        )
        return search_result[0].payload["data"] if search_result else "" 