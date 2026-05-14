import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { InteractionsService } from './interactions.service';
import { InteractionsController } from './interactions.controller';
import { Interaction, InteractionSchema } from './schemas/interaction.schema';

@Module({
  imports: [MongooseModule.forFeature([{ name: Interaction.name, schema: InteractionSchema }])],
  controllers: [InteractionsController],
  providers: [InteractionsService],
  exports: [InteractionsService],
})
export class InteractionsModule {}
