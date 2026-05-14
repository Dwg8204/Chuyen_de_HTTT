import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { Track, TrackDocument } from './schemas/track.schema';

@Injectable()
export class TracksService {
  constructor(
    @InjectModel(Track.name) private trackModel: Model<TrackDocument>,
    private httpService: HttpService,
  ) {}

  async findById(id: string): Promise<TrackDocument> {
    const track = await this.trackModel.findById(id);
    if (!track) throw new NotFoundException('Track not found');
    return track;
  }

  async findByIds(ids: string[]): Promise<TrackDocument[]> {
    return this.trackModel.find({ _id: { $in: ids } });
  }

  async search(q: string, limit = 20): Promise<TrackDocument[]> {
    // Thử text search trước (nếu có text index)
    try {
      const results = await this.trackModel
        .find({ $text: { $search: q } }, { score: { $meta: 'textScore' } })
        .sort({ score: { $meta: 'textScore' } })
        .limit(limit);
      if (results.length > 0) return results;
    } catch (_) {
      // Text index chưa tạo → fall through to regex
    }
    // Regex fallback: tìm trong title, artist, album
    const regex = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    return this.trackModel
      .find({ $or: [{ title: regex }, { artist: regex }, { album: regex }] })
      .sort({ total_plays: -1 })
      .limit(limit);
  }

  async getItunesPreview(trackId: string): Promise<{ previewUrl: string | null; artworkUrl: string | null }> {
    const track = await this.findById(trackId);
    const term = encodeURIComponent(`${track.artist} ${track.title}`);
    const url = `https://itunes.apple.com/search?term=${term}&media=music&limit=5`;
    try {
      const res = await firstValueFrom(this.httpService.get(url));
      const results = res.data?.results ?? [];
      for (const r of results) {
        if (r.previewUrl) {
          return {
            previewUrl: r.previewUrl,
            artworkUrl: r.artworkUrl100?.replace('100x100', '300x300') ?? null,
          };
        }
      }
    } catch {
      /* Return null if iTunes is unavailable */
    }
    return { previewUrl: null, artworkUrl: null };
  }

  async count() {
    return this.trackModel.countDocuments();
  }

  async findPopular(limit = 10): Promise<TrackDocument[]> {
    return this.trackModel.find().sort({ total_plays: -1 }).limit(limit);
  }
}
