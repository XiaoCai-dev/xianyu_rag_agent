import sqlite3
import os
import json
from datetime import datetime
from loguru import logger


class ChatContextManager:
    """
    聊天上下文管理器
    
    负责存储和检索用户与商品之间的对话历史，使用SQLite数据库进行持久化存储。
    支持按会话ID检索对话历史，以及议价次数统计。
    """
    
    def __init__(self, max_history=100, db_path="data/chat_history.db"):
        """
        初始化聊天上下文管理器
        
        Args:
            max_history: 每个对话保留的最大消息数
            db_path: SQLite数据库文件路径
        """
        self.max_history = max_history
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """初始化数据库表结构"""
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建消息表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            chat_id TEXT
        )
        ''')
        
        # 检查是否需要添加chat_id字段（兼容旧数据库）
        cursor.execute("PRAGMA table_info(messages)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'chat_id' not in columns:
            cursor.execute('ALTER TABLE messages ADD COLUMN chat_id TEXT')
            logger.info("已为messages表添加chat_id字段")
        if 'intent' not in columns:
            cursor.execute('ALTER TABLE messages ADD COLUMN intent TEXT')
            logger.info("已为messages表添加intent字段")

        # 创建索引以加速查询
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_user_item ON messages (user_id, item_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_chat_id ON messages (chat_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp ON messages (timestamp)
        ''')
        
        # 创建基于会话ID的议价次数表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_bargain_counts (
            chat_id TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建商品信息表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            item_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            price REAL,
            description TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # RAG 知识库文档元数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rag_documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT,
            scope TEXT NOT NULL DEFAULT 'shop',
            item_id TEXT,
            source TEXT NOT NULL DEFAULT 'manual_upload',
            chunk_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_rag_scope ON rag_documents (scope)
        ''')
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_rag_item ON rag_documents (item_id)
        ''')

        # 进程间控制命令队列（可视化平台 -> 主进程）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS control_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            payload TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            executed_at DATETIME
        )
        ''')
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_control_status ON control_queue (status)
        ''')

        conn.commit()
        conn.close()
        logger.info(f"聊天历史数据库初始化完成: {self.db_path}")
        

            
    def save_item_info(self, item_id, item_data):
        """
        保存商品信息到数据库
        
        Args:
            item_id: 商品ID
            item_data: 商品信息字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 从商品数据中提取有用信息
            price = float(item_data.get('soldPrice', 0))
            description = item_data.get('desc', '')
            
            # 将整个商品数据转换为JSON字符串
            data_json = json.dumps(item_data, ensure_ascii=False)
            
            cursor.execute(
                """
                INSERT INTO items (item_id, data, price, description, last_updated) 
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(item_id) 
                DO UPDATE SET data = ?, price = ?, description = ?, last_updated = ?
                """,
                (
                    item_id, data_json, price, description, datetime.now().isoformat(),
                    data_json, price, description, datetime.now().isoformat()
                )
            )
            
            conn.commit()
            logger.debug(f"商品信息已保存: {item_id}")
        except Exception as e:
            logger.error(f"保存商品信息时出错: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_item_info(self, item_id):
        """
        从数据库获取商品信息
        
        Args:
            item_id: 商品ID
            
        Returns:
            dict: 商品信息字典，如果不存在返回None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT data FROM items WHERE item_id = ?",
                (item_id,)
            )
            
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            return None
        except Exception as e:
            logger.error(f"获取商品信息时出错: {e}")
            return None
        finally:
            conn.close()

    def add_message_by_chat(self, chat_id, user_id, item_id, role, content, intent=None):
        """
        基于会话ID添加新消息到对话历史
        
        Args:
            chat_id: 会话ID
            user_id: 用户ID (用户消息存真实user_id，助手消息存卖家ID)
            item_id: 商品ID
            role: 消息角色 (user/assistant)
            content: 消息内容
            intent: 意图标签(仅assistant消息记录，用于仪表盘统计)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 插入新消息，使用chat_id作为额外标识
            cursor.execute(
                "INSERT INTO messages (user_id, item_id, role, content, timestamp, chat_id, intent) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, item_id, role, content, datetime.now().isoformat(), chat_id, intent)
            )
            
            # 检查是否需要清理旧消息（基于chat_id）
            cursor.execute(
                """
                SELECT id FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?, 1
                """, 
                (chat_id, self.max_history)
            )
            
            oldest_to_keep = cursor.fetchone()
            if oldest_to_keep:
                cursor.execute(
                    "DELETE FROM messages WHERE chat_id = ? AND id < ?",
                    (chat_id, oldest_to_keep[0])
                )
            
            conn.commit()
        except Exception as e:
            logger.error(f"添加消息到数据库时出错: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_context_by_chat(self, chat_id):
        """
        基于会话ID获取对话历史
        
        Args:
            chat_id: 会话ID
            
        Returns:
            list: 包含对话历史的列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                SELECT role, content FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp ASC
                LIMIT ?
                """, 
                (chat_id, self.max_history)
            )
            
            messages = [{"role": role, "content": content} for role, content in cursor.fetchall()]
            
            # 获取议价次数并添加到上下文中
            bargain_count = self.get_bargain_count_by_chat(chat_id)
            if bargain_count > 0:
                messages.append({
                    "role": "system", 
                    "content": f"议价次数: {bargain_count}"
                })
            
        except Exception as e:
            logger.error(f"获取对话历史时出错: {e}")
            messages = []
        finally:
            conn.close()
        
        return messages

    def increment_bargain_count_by_chat(self, chat_id):
        """
        基于会话ID增加议价次数
        
        Args:
            chat_id: 会话ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 使用UPSERT语法直接基于chat_id增加议价次数
            cursor.execute(
                """
                INSERT INTO chat_bargain_counts (chat_id, count, last_updated)
                VALUES (?, 1, ?)
                ON CONFLICT(chat_id) 
                DO UPDATE SET count = count + 1, last_updated = ?
                """,
                (chat_id, datetime.now().isoformat(), datetime.now().isoformat())
            )
            
            conn.commit()
            logger.debug(f"会话 {chat_id} 议价次数已增加")
        except Exception as e:
            logger.error(f"增加议价次数时出错: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_bargain_count_by_chat(self, chat_id):
        """
        基于会话ID获取议价次数
        
        Args:
            chat_id: 会话ID
            
        Returns:
            int: 议价次数
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT count FROM chat_bargain_counts WHERE chat_id = ?",
                (chat_id,)
            )

            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"获取议价次数时出错: {e}")
            return 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # RAG 知识库文档元数据 CRUD
    # ------------------------------------------------------------------
    def add_rag_document(self, title, scope, item_id, source, chunk_count):
        """登记一条 RAG 文档记录，返回 doc_id。"""
        import uuid
        doc_id = uuid.uuid4().hex
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO rag_documents (doc_id, title, scope, item_id, source, chunk_count, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
                (doc_id, title, scope, item_id, source, chunk_count, datetime.now().isoformat()),
            )
            conn.commit()
            logger.debug(f"RAG 文档登记: doc_id={doc_id}, title={title}, chunks={chunk_count}")
            return doc_id
        except Exception as e:
            logger.error(f"登记 RAG 文档时出错: {e}")
            conn.rollback()
            return doc_id
        finally:
            conn.close()

    def list_rag_documents(self, scope=None, item_id=None):
        """列出 RAG 文档记录，可按 scope/item_id 过滤。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sql = "SELECT * FROM rag_documents WHERE status='active'"
            params = []
            if scope:
                sql += " AND scope=?"
                params.append(scope)
            if item_id:
                sql += " AND item_id=?"
                params.append(item_id)
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"列出 RAG 文档时出错: {e}")
            return []
        finally:
            conn.close()

    def delete_rag_document(self, doc_id):
        """软删除 RAG 文档记录（置 status=deleted）。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE rag_documents SET status='deleted' WHERE doc_id=?",
                (doc_id,),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"删除 RAG 文档时出错: {e}")
            conn.rollback()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 进程间控制命令队列（可视化平台写，主进程读并执行）
    # ------------------------------------------------------------------
    def enqueue_control(self, command, payload=None):
        """写入一条控制命令，返回命令 id。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO control_queue (command, payload, status, created_at) VALUES (?, ?, 'pending', ?)",
                (command, json.dumps(payload, ensure_ascii=False) if payload else None, datetime.now().isoformat()),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"写入控制命令时出错: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def fetch_pending_controls(self, limit=10):
        """拉取待执行命令。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM control_queue WHERE status='pending' ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"拉取控制命令时出错: {e}")
            return []
        finally:
            conn.close()

    def ack_control(self, control_id, status='done', result=None):
        """回写命令执行结果。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE control_queue SET status=?, result=?, executed_at=? WHERE id=?",
                (status, result, datetime.now().isoformat(), control_id),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"回写控制命令时出错: {e}")
            conn.rollback()
        finally:
            conn.close()