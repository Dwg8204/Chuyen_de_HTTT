import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document, Types } from 'mongoose';

export type InteractionDocument = Interaction & Document;

@Schema()
export class Interaction {
  @Prop({ type: Types.ObjectId, ref: 'User', required: true })
  user_id: Types.ObjectId;

  @Prop({ type: Types.ObjectId, ref: 'Track', required: true })
  track_id: Types.ObjectId;

  @Prop({ default: 0 })
  play_count: number;

  @Prop({ default: () => new Date() })
  last_played: Date;
}

export const InteractionSchema = SchemaFactory.createForClass(Interaction);
InteractionSchema.index({ user_id: 1, track_id: 1 }, { unique: true });
