import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleInit, OnModuleDestroy {
  private client: Redis;

  onModuleInit() {
    this.client = new Redis({
      host: process.env.REDIS_HOST ?? 'localhost',
      port: parseInt(process.env.REDIS_PORT ?? '6379'),
    });
  }

  onModuleDestroy() {
    this.client.disconnect();
  }

  /** Thêm trackId vào đầu list recent_tracks, giữ tối đa 10, reset TTL 30 phút */
  async pushRecentTrack(userId: string, trackId: string): Promise<void> {
    const key = `session:${userId}:recent_tracks`;
    await this.client.lpush(key, trackId);
    await this.client.ltrim(key, 0, 9);          // Giữ 10 bài gần nhất
    await this.client.expire(key, 1800);          // Sliding window 30 phút
  }

  /** Lấy danh sách recent_tracks của user */
  async getRecentTracks(userId: string): Promise<string[]> {
    const key = `session:${userId}:recent_tracks`;
    return this.client.lrange(key, 0, -1);
  }

  /** Xóa recent_tracks của user */
  async clearRecentTracks(userId: string): Promise<void> {
    await this.client.del(`session:${userId}:recent_tracks`);
  }
}
