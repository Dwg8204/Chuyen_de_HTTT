import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type TrackDocument = Track & Document;

@Schema()
export class Track {
  @Prop({ required: true, unique: true })
  track_id_str: string;

  @Prop({ required: true })
  title: string;

  @Prop({ required: true })
  artist: string;

  @Prop({ type: [String], default: [] })
  genre: string[];

  @Prop({
    type: {
      danceability: Number,
      energy: Number,
      valence: Number,
      tempo: Number,
      acousticness: Number,
      liveness: Number,
      speechiness: Number,
    },
    default: {},
  })
  audio_features: Record<string, number>;

  @Prop({ type: [Number], default: [] })
  content_vector: number[];

  @Prop({ default: 0 })
  total_plays: number;

  @Prop({ default: 50 })
  popularity: number;
}

export const TrackSchema = SchemaFactory.createForClass(Track);
