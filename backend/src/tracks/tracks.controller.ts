import { Controller, Get, Param, Query, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { TracksService } from './tracks.service';

@UseGuards(JwtAuthGuard)
@Controller('tracks')
export class TracksController {
  constructor(private tracksService: TracksService) {}

  @Get('search')
  search(
    @Query('q') q: string,
    @Query('limit') limit = '20',
    @Query('genre') genre?: string,
  ) {
    return this.tracksService.search(q, parseInt(limit), genre);
  }

  @Get('genres')
  getGenres() {
    return this.tracksService.findDistinctGenres();
  }

  @Get('artists')
  getArtists(@Query('q') q: string, @Query('limit') limit = '10') {
    return this.tracksService.findArtists(q, parseInt(limit));
  }

  @Get(':id/itunes-preview')
  getPreview(@Param('id') id: string) {
    return this.tracksService.getItunesPreview(id);
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.tracksService.findById(id);
  }
}
