import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { User, UserDocument } from './schemas/user.schema';

@Injectable()
export class UsersService {
  constructor(@InjectModel(User.name) private userModel: Model<UserDocument>) {}

  async findById(id: string): Promise<UserDocument> {
    const user = await this.userModel.findById(id).select('-password');
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  async updateOnboarding(userId: string, data: { favorite_genres: string[]; mood: string }) {
    return this.userModel.findByIdAndUpdate(
      userId,
      { $set: { onboarding_preferences: data } },
      { new: true, select: '-password' },
    );
  }

  async updateProfile(userId: string, data: { age?: number; gender?: string; location?: string }) {
    return this.userModel.findByIdAndUpdate(
      userId,
      { $set: { demographics: data } },
      { new: true, select: '-password' },
    );
  }

  async findAll(page = 1, limit = 20) {
    const skip = (page - 1) * limit;
    const [users, total] = await Promise.all([
      this.userModel.find().select('-password').skip(skip).limit(limit).sort({ createdAt: -1 }),
      this.userModel.countDocuments(),
    ]);
    return { users, total, page, limit };
  }

  async deleteUser(id: string) {
    await this.userModel.findByIdAndDelete(id);
    return { message: 'User deleted' };
  }

  async count() {
    return this.userModel.countDocuments();
  }
}
