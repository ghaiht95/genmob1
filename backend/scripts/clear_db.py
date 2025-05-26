#!/usr/bin/env python3
"""
سكريبت بسيط لتفريغ قاعدة البيانات وإعادة تهيئتها بجداول فارغة
"""
import asyncio
import logging
from database import clear_database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("بدء عملية تفريغ قاعدة البيانات...")
    await clear_database()
    logger.info("اكتملت العملية.")

if __name__ == "__main__":
    asyncio.run(main()) 