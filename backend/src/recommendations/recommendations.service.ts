import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { RedisService } from '../common/redis/redis.service';
import { TracksService } from '../tracks/tracks.service';
import { User, UserDocument } from '../users/schemas/user.schema';

@Injectable()
export class RecommendationsService {
  private readonly aiUrl = process.env.AI_SERVICE_URL ?? 'http://localhost:8000';

  constructor(
    @InjectModel(User.name) private userModel: Model<UserDocument>,
    private httpService: HttpService,
    private redisService: RedisService,
    private tracksService: TracksService,
  ) {}

  async getHybridRecommendations(userId: string) {
    const recentIds = await this.redisService.getRecentTracks(userId);
    const user = await this.userModel.findById(userId);

    let trackIds: string[] = [];

    if (recentIds.length > 0) {
      // Try hybrid recommend
      try {
        const res = await firstValueFrom(
          this.httpService.get(`${this.aiUrl}/ai/hybrid-recommend`, {
            params: { user_id: userId, recent_tracks: recentIds.join(',') },
            timeout: 10000,
          }),
        );
        trackIds = res.data?.track_ids ?? [];
      } catch { /* fallback below */ }
    }

    if (trackIds.length === 0) {
      // Cold-start fallback
      const genres = user?.onboarding_preferences?.favorite_genres ?? [];
      try {
        const res = await firstValueFrom(
          this.httpService.get(`${this.aiUrl}/ai/cold-start`, {
            params: { genres: genres.join(','), top_k: 30 },
            timeout: 10000,
          }),
        );
        trackIds = res.data?.track_ids ?? [];
      } catch { /* if AI down, return popular */ }
    }

    if (trackIds.length === 0) {
      const popular = await this.tracksService.findPopular(30);
      return popular;
    }

    // Fetch full track metadata
    const tracks = await this.tracksService.findByIds(trackIds);
    // Preserve AI ordering
    const map = new Map(tracks.map((t) => [t._id.toString(), t]));
    return trackIds.map((id) => map.get(id)).filter(Boolean);
  }

  async getSimilarTracks(trackId: string, recentIds: string[] = []) {
    try {
      const res = await firstValueFrom(
        this.httpService.get(`${this.aiUrl}/ai/content-similar`, {
          params: { track_id: trackId, top_k: 5, exclude: recentIds.join(',') },
          timeout: 8000,
        }),
      );
      const similar: { track_id: string; score: number }[] = res.data?.similar_tracks ?? [];
      const ids = similar.map((s) => s.track_id);
      const tracks = await this.tracksService.findByIds(ids);
      const map = new Map(tracks.map((t) => [t._id.toString(), t]));
      return ids.map((id) => map.get(id)).filter(Boolean);
    } catch {
      return [];
    }
  }
}
