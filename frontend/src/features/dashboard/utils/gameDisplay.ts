import { Game, User } from '@/types';

export interface AnalyzingGameInfo {
  id: number;
  opponent: string;
  result: string;
  timeClass: string;
  date?: string;
}

export function getUserColor(game: Game, chesscomUsername: string | null | undefined): 'white' | 'black' {
  if (game.white_username?.toLowerCase() === chesscomUsername?.toLowerCase()) {
    return 'white';
  }
  return 'black';
}

export function getOpponentUsername(game: Game, chesscomUsername: string | null | undefined): string {
  const userColor = getUserColor(game, chesscomUsername);
  return userColor === 'white' ? game.black_username || 'Unknown' : game.white_username || 'Unknown';
}

export function getUserResult(game: Game, chesscomUsername: string | null | undefined): string | undefined {
  const userColor = getUserColor(game, chesscomUsername);
  return userColor === 'white' ? game.white_result : game.black_result;
}

export function formatGameResult(userResult: string | undefined): { label: string; colorClass: string } {
  if (userResult === 'win') {
    return { label: '🎉 Win', colorClass: 'text-green-400' };
  }
  if (userResult === 'checkmated' || userResult === 'resigned' || userResult === 'timeout') {
    return { label: '❌ Loss', colorClass: 'text-red-400' };
  }
  return { label: '🤝 Draw', colorClass: 'text-gray-400' };
}

export function toAnalyzingGameInfo(game: Game, user: User): AnalyzingGameInfo {
  const userColor = getUserColor(game, user.chesscom_username);
  const opponent = getOpponentUsername(game, user.chesscom_username);

  let result = 'draw';
  if (userColor === 'white') {
    if (game.winner === 'white') result = 'win';
    else if (game.winner === 'black') result = 'loss';
  } else {
    if (game.winner === 'black') result = 'win';
    else if (game.winner === 'white') result = 'loss';
  }

  return {
    id: game.id,
    opponent,
    result,
    timeClass: game.time_class || 'unknown',
    date: game.end_time,
  };
}
