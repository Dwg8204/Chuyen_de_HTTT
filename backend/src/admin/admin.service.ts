import { Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { UsersService } from '../users/users.service';
import { TracksService } from '../tracks/tracks.service';
import { InteractionsService } from '../interactions/interactions.service';

@Injectable()
export class AdminService {
  private readonly aiUrl = process.env.AI_SERVICE_URL ?? 'http://localhost:8000';

  constructor(
    private httpService: HttpService,
    private usersService: UsersService,
    private tracksService: TracksService,
    private interactionsService: InteractionsService,
  ) {}

  async getStats() {
    const [total_users, total_tracks, total_interactions] = await Promise.all([
      this.usersService.count(),
      this.tracksService.count(),
      this.interactionsService.count(),
    ]);
    return { total_users, total_tracks, total_interactions };
  }

  async triggerTraining() {
    const res = await firstValueFrom(
      this.httpService.post(`${this.aiUrl}/ai/train`, {}, { timeout: 600_000 }),
    );
    return res.data;
  }

  async runEvaluation() {
    const res = await firstValueFrom(
      this.httpService.get(`${this.aiUrl}/ai/evaluate`, { timeout: 300_000 }),
    );
    return res.data;
  }

  async runCbEvaluation() {
    const res = await firstValueFrom(
      this.httpService.get(`${this.aiUrl}/ai/evaluate/cb`, { timeout: 300_000 }),
    );
    return res.data;
  }

  async listUsers(page = 1, limit = 20) {
    return this.usersService.findAll(page, limit);
  }

  async deleteUser(id: string) {
    return this.usersService.deleteUser(id);
  }
}
