import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { MongooseModule } from '@nestjs/mongoose';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { TracksModule } from './tracks/tracks.module';
import { InteractionsModule } from './interactions/interactions.module';
import { RecommendationsModule } from './recommendations/recommendations.module';
import { AdminModule } from './admin/admin.module';
import { RedisModule } from './common/redis/redis.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    MongooseModule.forRoot(process.env.MONGO_URI ?? 'mongodb://localhost:27017/musicrec', {
      dbName: process.env.DB_NAME ?? 'musicrec',
    }),
    RedisModule,
    AuthModule,
    UsersModule,
    TracksModule,
    InteractionsModule,
    RecommendationsModule,
    AdminModule,
  ],
})
export class AppModule {}
