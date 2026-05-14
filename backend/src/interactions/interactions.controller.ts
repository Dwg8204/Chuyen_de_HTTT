import { Controller, Post, Param, Request, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { InteractionsService } from './interactions.service';

@UseGuards(JwtAuthGuard)
@Controller('play')
export class InteractionsController {
  constructor(private interactionsService: InteractionsService) {}

  @Post(':trackId')
  async recordPlay(@Param('trackId') trackId: string, @Request() req) {
    // Fire and forget — respond immediately
    this.interactionsService.recordPlay(req.user.userId, trackId).catch(() => {});
    return { ok: true };
  }
}
