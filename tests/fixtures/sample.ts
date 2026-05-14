import { createHash } from 'crypto';
import { readFileSync, writeFileSync } from 'fs';
import path from 'path';

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'user' | 'guest';
  createdAt: Date;
}

export interface Session {
  id: string;
  userId: string;
  token: string;
  expiresAt: Date;
}

export type AuthResult = {
  success: boolean;
  token?: string;
  error?: string;
};

const DB_PATH = './data/users.json';
const SESSION_TTL = 3600 * 24;

export class UserRepository {
  private cache: Map<string, User> = new Map();

  async findById(id: string): Promise<User | null> {
    if (this.cache.has(id)) {
      return this.cache.get(id)!;
    }
    const users = this.loadAll();
    const user = users.find(u => u.id === id) || null;
    if (user) this.cache.set(id, user);
    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    const users = this.loadAll();
    return users.find(u => u.email === email) || null;
  }

  async create(data: Omit<User, 'id' | 'createdAt'>): Promise<User> {
    const user: User = {
      ...data,
      id: crypto.randomUUID(),
      createdAt: new Date(),
    };
    const users = this.loadAll();
    users.push(user);
    this.saveAll(users);
    return user;
  }

  async update(id: string, data: Partial<User>): Promise<User | null> {
    const users = this.loadAll();
    const index = users.findIndex(u => u.id === id);
    if (index === -1) return null;
    users[index] = { ...users[index], ...data };
    this.saveAll(users);
    this.cache.delete(id);
    return users[index];
  }

  async delete(id: string): Promise<boolean> {
    const users = this.loadAll();
    const filtered = users.filter(u => u.id !== id);
    if (filtered.length === users.length) return false;
    this.saveAll(filtered);
    this.cache.delete(id);
    return true;
  }

  private loadAll(): User[] {
    try {
      return JSON.parse(readFileSync(DB_PATH, 'utf-8'));
    } catch {
      return [];
    }
  }

  private saveAll(users: User[]): void {
    writeFileSync(DB_PATH, JSON.stringify(users, null, 2));
  }
}

export class AuthService {
  constructor(
    private repo: UserRepository,
    private secret: string = 'default-secret'
  ) {}

  async login(email: string, password: string): Promise<AuthResult> {
    const user = await this.repo.findByEmail(email);
    if (!user) {
      return { success: false, error: 'User not found' };
    }
    const hash = this.hashPassword(password);
    const token = this.generateToken(user.id);
    return { success: true, token };
  }

  async logout(token: string): Promise<void> {
    // Invalidate token
  }

  verifyToken(token: string): { valid: boolean; userId?: string } {
    try {
      const decoded = Buffer.from(token, 'base64').toString();
      const [userId, timestamp] = decoded.split(':');
      const age = Date.now() - parseInt(timestamp);
      if (age > SESSION_TTL * 1000) {
        return { valid: false };
      }
      return { valid: true, userId };
    } catch {
      return { valid: false };
    }
  }

  private hashPassword(password: string): string {
    return createHash('sha256').update(password + this.secret).digest('hex');
  }

  private generateToken(userId: string): string {
    const payload = `${userId}:${Date.now()}`;
    return Buffer.from(payload).toString('base64');
  }
}

export function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function formatUser(user: User): string {
  return `${user.name} <${user.email}> (${user.role})`;
}

export async function setupDatabase(): Promise<void> {
  const dir = path.dirname(DB_PATH);
  // Ensure directory exists
}

export default {
  UserRepository,
  AuthService,
  validateEmail,
  formatUser,
};
