import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model, Types } from 'mongoose';
import { Interaction, InteractionDocument } from './schemas/interaction.schema';
import { RedisService } from '../common/redis/redis.service';

@Injectable()
export class InteractionsService {
  constructor(
    @InjectModel(Interaction.name) private interactionModel: Model<InteractionDocument>,
    private redisService: RedisService,
  ) {}

  async recordPlay(userId: string, trackId: string): Promise<void> {
    const uid = new Types.ObjectId(userId);
    const tid = new Types.ObjectId(trackId);

    // Upsert interaction (increment play_count, update last_played)
    await this.interactionModel.findOneAndUpdate(
      { user_id: uid, track_id: tid },
      {
        $inc: { play_count: 1 },
        $set: { last_played: new Date() },
      },
      { upsert: true },
    );

    // Update Redis session (sliding window, non-blocking)
    this.redisService.pushRecentTrack(userId, trackId).catch(() => {});
  }

  async count() {
    return this.interactionModel.countDocuments();
  }
}
