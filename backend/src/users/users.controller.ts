import { Controller, Get, Put, Body, Request, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { UsersService } from './users.service';

@UseGuards(JwtAuthGuard)
@Controller('users')
export class UsersController {
  constructor(private usersService: UsersService) {}

  @Get('me')
  getMe(@Request() req) {
    return this.usersService.findById(req.user.userId);
  }

  @Put('me/onboarding')
  updateOnboarding(
    @Request() req,
    @Body() body: { favorite_genres: string[]; mood: string },
  ) {
    return this.usersService.updateOnboarding(req.user.userId, body);
  }

  @Put('me/profile')
  updateProfile(
    @Request() req,
    @Body() body: { age?: number; gender?: string; location?: string },
  ) {
    return this.usersService.updateProfile(req.user.userId, body);
  }
}
