import { Injectable, ConflictException, UnauthorizedException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcrypt';
import { User, UserDocument } from '../users/schemas/user.schema';
import { RegisterDto, LoginDto } from './dto/auth.dto';

@Injectable()
export class AuthService {
  constructor(
    @InjectModel(User.name) private userModel: Model<UserDocument>,
    private jwtService: JwtService,
  ) {}

  async register(dto: RegisterDto) {
    const exists = await this.userModel.findOne({ username: dto.username });
    if (exists) throw new ConflictException('Username already taken');

    const hashed = await bcrypt.hash(dto.password, 10);
    const user = await this.userModel.create({ username: dto.username, password: hashed });

    const token = this._sign(user);
    return { access_token: token, user: this._safeUser(user) };
  }

  async login(dto: LoginDto) {
    const user = await this.userModel.findOne({ username: dto.username });
    if (!user) throw new UnauthorizedException('Invalid credentials');

    const valid = await bcrypt.compare(dto.password, user.password);
    if (!valid) throw new UnauthorizedException('Invalid credentials');

    const token = this._sign(user);
    return { access_token: token, user: this._safeUser(user) };
  }

  private _sign(user: UserDocument) {
    return this.jwtService.sign({
      sub: user._id.toString(),
      username: user.username,
      role: user.role,
    });
  }

  private _safeUser(user: UserDocument) {
    return {
      id: user._id.toString(),
      username: user.username,
      role: user.role,
      onboarding_preferences: user.onboarding_preferences,
    };
  }
}
