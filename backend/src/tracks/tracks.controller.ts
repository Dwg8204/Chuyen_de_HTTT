import { Controller, Get, Param, Query, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { TracksService } from './tracks.service';

@UseGuards(JwtAuthGuard)
@Controller('tracks')
export class TracksController {
  constructor(private tracksService: TracksService) {}

  @Get('search')
  search(@Query('q') q: string, @Query('limit') limit = '20') {
    return this.tracksService.search(q, parseInt(limit));
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.tracksService.findById(id);
  }

  @Get(':id/itunes-preview')
  getPreview(@Param('id') id: string) {
    return this.tracksService.getItunesPreview(id);
  }
}
