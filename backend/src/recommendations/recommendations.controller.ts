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

  /** Trang chủ: Hybrid (CF + CB) */
  @Get()
  getRecommendations(@Request() req) {
    return this.recommendationsService.getHybridRecommendations(req.user.userId);
  }

  /** Tab "Collab Picks": Collaborative Filtering only */
  @Get('collab')
  getCollab(@Request() req) {
    return this.recommendationsService.getCollabRecommendations(req.user.userId);
  }

  /** Tab "Taste Match": Content-Based only */
  @Get('content')
  getContent(@Request() req) {
    return this.recommendationsService.getContentRecommendations(req.user.userId);
  }

  /** Similar tracks popup khi nghe (Hybrid) */
  @Get('similar/:trackId')
  async getSimilar(@Param('trackId') trackId: string, @Request() req) {
    const recentIds = await this.redisService.getRecentTracks(req.user.userId);
    return this.recommendationsService.getSimilarTracks(trackId, req.user.userId, recentIds);
  }
}
