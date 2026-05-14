import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { AdminService } from './admin.service';
import { AdminController } from './admin.controller';
import { UsersModule } from '../users/users.module';
import { TracksModule } from '../tracks/tracks.module';
import { InteractionsModule } from '../interactions/interactions.module';

@Module({
  imports: [HttpModule, UsersModule, TracksModule, InteractionsModule],
  controllers: [AdminController],
  providers: [AdminService],
})
export class AdminModule {}
