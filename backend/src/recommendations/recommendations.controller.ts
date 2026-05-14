import { Controller, Get, Param, Request, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { RecommendationsService } from './recommendations.service';
import { RedisService } from '../common/redis/redis.service';

@UseGuards(JwtAuthGuard)
@Controller('recommendations')
export class RecommendationsController {
  constructor(
    private recommendationsService: RecommendationsService,
    private redisService: RedisService,
  ) {}

  @Get()
  getRecommendations(@Request() req) {
    return this.recommendationsService.getHybridRecommendations(req.user.userId);
  }

  @Get('similar/:trackId')
  async getSimilar(@Param('trackId') trackId: string, @Request() req) {
    const recentIds = await this.redisService.getRecentTracks(req.user.userId);
    return this.recommendationsService.getSimilarTracks(trackId, recentIds);
  }
}
