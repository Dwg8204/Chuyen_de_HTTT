import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { Track, TrackDocument } from './schemas/track.schema';

/** Chuẩn hoá chuỗi tiếng Việt: bỏ dấu, lowercase
 *  vd: "Sơn Tùng" → "son tung"  */
function normalizeVi(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // bỏ combining diacritics
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim();
}

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

  /**
   * Tìm kiếm hỗ trợ tiếng Việt không dấu:
   * - Chuẩn hoá query về không dấu
   * - Dùng regex trên trường title, artist
   * - Nếu có genre → lọc thêm theo genre
   */
  async search(q: string, limit = 20, genre?: string): Promise<TrackDocument[]> {
    const normQ = normalizeVi(q ?? '');

    // Thử MongoDB text search trước (có dấu, nhanh)
    if (!genre) {
      try {
        const results = await this.trackModel
          .find({ $text: { $search: q } }, { score: { $meta: 'textScore' } })
          .sort({ score: { $meta: 'textScore' } })
          .limit(limit);
        if (results.length > 0) return results;
      } catch (_) { /* text index chưa tạo → fallback */ }
    }

    // Regex không dấu: match bất kỳ vị trí trong chuỗi đã normalize
    // MongoDB không hỗ trợ normalize natively → fetch + filter JS-side (với limit * 10)
    const fetchLimit = Math.min(limit * 10, 2000);
    const genreFilter = genre ? { genre: { $in: [genre] } } : {};
    const candidates = await this.trackModel
      .find(genreFilter)
      .sort({ total_plays: -1 })
      .limit(fetchLimit)
      .lean();

    const filtered = candidates.filter((t: any) => {
      const titleNorm  = normalizeVi(t.title  ?? '');
      const artistNorm = normalizeVi(t.artist ?? '');
      return titleNorm.includes(normQ) || artistNorm.includes(normQ);
    });

    return filtered.slice(0, limit) as unknown as TrackDocument[];
  }

  /** Trả về danh sách genre unique từ DB */
  async findDistinctGenres(): Promise<string[]> {
    const genres = await this.trackModel.distinct('genre');
    return genres.filter(Boolean).sort();
  }

  /** Tìm artist theo query (để autocomplete trong profile) */
  async findArtists(q: string, limit = 10): Promise<{ artist: string }[]> {
    const normQ = normalizeVi(q);
    const candidates = await this.trackModel
      .distinct('artist');

    const matched = (candidates as string[])
      .filter((a) => normalizeVi(a).includes(normQ))
      .slice(0, limit)
      .map((artist) => ({ artist }));
    return matched;
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
    } catch { /* Return null if iTunes is unavailable */ }
    return { previewUrl: null, artworkUrl: null };
  }

  async count() {
    return this.trackModel.countDocuments();
  }

  async findPopular(limit = 10): Promise<TrackDocument[]> {
    return this.trackModel.find().sort({ total_plays: -1 }).limit(limit);
  }
}
