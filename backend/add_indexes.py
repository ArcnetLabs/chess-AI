"""
Add database indexes for game filtering performance.
Run this script to add indexes to your SQLite database.
"""
from sqlalchemy import create_engine, Index, inspect
from app.models import Game
from app.core.database import engine, Base
from loguru import logger

def add_indexes():
    """Add indexes to games table for better filter performance."""
    
    inspector = inspect(engine)
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('games')}
    
    logger.info(f"📊 Current indexes on 'games' table: {existing_indexes}")
    
    # Define indexes to create (only using existing fields)
    indexes_to_create = [
        Index('idx_games_user_id', Game.user_id),
        Index('idx_games_time_class', Game.time_class),
        Index('idx_games_end_time', Game.end_time),
        Index('idx_games_is_analyzed', Game.is_analyzed),
        Index('idx_games_winner', Game.winner),
        Index('idx_games_user_time_class', Game.user_id, Game.time_class),
        Index('idx_games_user_end_time', Game.user_id, Game.end_time),
        Index('idx_games_user_analyzed', Game.user_id, Game.is_analyzed),
        Index('idx_games_user_time_winner', Game.user_id, Game.time_class, Game.winner),
    ]
    
    created_count = 0
    skipped_count = 0
    
    with engine.begin() as connection:
        for index in indexes_to_create:
            if index.name in existing_indexes:
                logger.info(f"⏭️  Index '{index.name}' already exists, skipping")
                skipped_count += 1
                continue
            
            try:
                index.create(connection)
                logger.info(f"✅ Created index: {index.name}")
                created_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to create index {index.name}: {e}")
    
    logger.info(f"\n🎉 Index creation complete!")
    logger.info(f"   Created: {created_count}")
    logger.info(f"   Skipped: {skipped_count}")
    logger.info(f"   Total: {len(indexes_to_create)}")
    
    # Verify indexes were created
    inspector = inspect(engine)
    final_indexes = {idx['name'] for idx in inspector.get_indexes('games')}
    logger.info(f"\n📊 Final indexes on 'games' table: {final_indexes}")

if __name__ == "__main__":
    logger.info("🚀 Starting index creation for games table...")
    logger.info(f"📁 Database: {engine.url}")
    
    add_indexes()
