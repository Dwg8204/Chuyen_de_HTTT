import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type UserDocument = User & Document;

@Schema({ timestamps: true })
export class User {
  @Prop({ required: true, unique: true, trim: true })
  username: string;

  @Prop({ required: true })
  password: string;

  @Prop({ default: 'user', enum: ['user', 'admin'] })
  role: string;

  @Prop({
    type: {
      age: Number,
      gender: String,
      location: String,
    },
    default: {},
  })
  demographics: {
    age?: number;
    gender?: string;
    location?: string;
  };

  @Prop({
    type: {
      favorite_genres:  [String],
      favorite_artists: [String],
      mood: String,
    },
    default: {},
  })
  onboarding_preferences: {
    favorite_genres?:  string[];
    favorite_artists?: string[];
    mood?: string;
  };
}

export const UserSchema = SchemaFactory.createForClass(User);
