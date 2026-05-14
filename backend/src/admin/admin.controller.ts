import { Controller, Get, Post, Delete, Param, Query, UseGuards, Request } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { RolesGuard } from '../auth/guards/roles.guard';
import { Roles } from '../auth/decorators/roles.decorator';
import { AdminService } from './admin.service';

@UseGuards(JwtAuthGuard, RolesGuard)
@Roles('admin')
@Controller('admin')
export class AdminController {
  constructor(private adminService: AdminService) {}

  @Get('stats')
  getStats() {
    return this.adminService.getStats();
  }

  @Post('trigger-training')
  triggerTraining() {
    return this.adminService.triggerTraining();
  }

  @Get('evaluate')
  evaluate() {
    return this.adminService.runEvaluation();
  }

  @Get('evaluate/cb')
  evaluateCb() {
    return this.adminService.runCbEvaluation();
  }

  @Get('users')
  listUsers(@Query('page') page = '1', @Query('limit') limit = '20') {
    return this.adminService.listUsers(parseInt(page), parseInt(limit));
  }

  @Delete('users/:id')
  deleteUser(@Param('id') id: string) {
    return this.adminService.deleteUser(id);
  }
}
