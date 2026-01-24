import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/router';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { TrendingUp, TrendingDown, Trophy, Target, AlertCircle, CheckCircle2, Brain, Clock, Zap } from 'lucide-react';
import api from '@/lib/api';
import { User, Analysis, MoveQualityStats, Game } from '@/types';
import toast from 'react-hot-toast';
import { AnalysisProgressModal } from '@/components/AnalysisProgressModal';

const MoveQualityChart: React.FC<{ data: MoveQualityStats }> = ({ data }) => {
  const chartData = [
    { name: 'Brilliant', value: data.brilliant_moves, fill: '#10b981' },
    { name: 'Great', value: data.great_moves, fill: '#22c55e' },
    { name: 'Best', value: data.best_moves, fill: '#84cc16' },
    { name: 'Excellent', value: data.excellent_moves, fill: '#eab308' },
    { name: 'Good', value: data.good_moves, fill: '#f59e0b' },
    { name: 'Inaccuracy', value: data.inaccuracies, fill: '#f97316' },
    { name: 'Mistake', value: data.mistakes, fill: '#ef4444' },
    { name: 'Blunder', value: data.blunders, fill: '#dc2626' },
  ].filter(item => item.value > 0);

  return (
    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
      <h3 className="text-lg font-semibold mb-4 text-white">Move Quality Distribution</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ backgroundColor: '#374151', border: 'none', borderRadius: '8px', color: '#fff' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

const PerformanceCard: React.FC<{
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  subtitle?: string;
}> = ({ title, value, change, icon, trend, subtitle }) => {
  const getTrendIcon = () => {
    if (trend === 'up') return <TrendingUp className="w-4 h-4 text-green-400" />;
    if (trend === 'down') return <TrendingDown className="w-4 h-4 text-red-400" />;
    return null;
  };

  return (
    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
          {change !== undefined && (
            <div className="flex items-center mt-2">
              {getTrendIcon()}
              <span className={`text-sm ml-1 ${
                trend === 'up' ? 'text-green-400' : 
                trend === 'down' ? 'text-red-400' : 
                'text-gray-400'
              }`}>
                {change > 0 ? '+' : ''}{change} from last week
              </span>
            </div>
          )}
        </div>
        <div className="text-blue-400">{icon}</div>
      </div>
    </div>
  );
};

const CoachingInsightCard: React.FC<{
  category: string;
  priority: 'high' | 'medium' | 'low';
  description: string;
  improvement: string;
}> = ({ category, priority, description, improvement }) => {
  const getPriorityColor = () => {
    switch (priority) {
      case 'high': return 'text-red-400 bg-red-900/20 border-red-800';
      case 'medium': return 'text-yellow-400 bg-yellow-900/20 border-yellow-800';
      case 'low': return 'text-green-400 bg-green-900/20 border-green-800';
    }
  };

  const getPriorityIcon = () => {
    switch (priority) {
      case 'high': return <AlertCircle className="w-5 h-5" />;
      case 'medium': return <Target className="w-5 h-5" />;
      case 'low': return <CheckCircle2 className="w-5 h-5" />;
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${getPriorityColor()}`}>
      <div className="flex items-start space-x-3">
        {getPriorityIcon()}
        <div className="flex-1">
          <h4 className="font-semibold capitalize text-white">{category.replace('_', ' ')}</h4>
          <p className="text-sm mt-1 text-gray-300">{description}</p>
          <p className="text-xs mt-2 font-medium">💡 {improvement}</p>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          priority === 'high' ? 'bg-red-800 text-red-200' :
          priority === 'medium' ? 'bg-yellow-800 text-yellow-200' :
          'bg-green-800 text-green-200'
        }`}>
          {priority.toUpperCase()}
        </span>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const router = useRouter();
  const { username } = router.query;
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);
  const [analyzingGamesCount, setAnalyzingGamesCount] = useState(0);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [gamesCollapsed, setGamesCollapsed] = useState(false);

  // Fetch user data by username (ensure lowercase for consistency)
  const normalizedUsername = username ? (username as string).toLowerCase() : '';
  const { data: userData, error: userError, isLoading: userLoading, refetch: refetchUserData } = useQuery({
    queryKey: ['user', normalizedUsername],
    queryFn: () => api.users.getByUsername(normalizedUsername),
    enabled: !!normalizedUsername,
  });

  // Fetch analysis summary
  const { data: analysisSummary, isLoading: summaryLoading, refetch: refetchAnalysisSummary } = useQuery({
    queryKey: ['analysis-summary', user?.id],
    queryFn: async () => {
      const summary = await api.analysis.getSummary(user!.id, 7);
      console.log('📊 Fetched analysis summary:', summary);
      return summary;
    },
    enabled: !!user?.id,
    staleTime: 0, // Don't cache - always fetch fresh data
    refetchOnWindowFocus: true, // Refetch when window regains focus
    refetchOnMount: true, // Refetch on component mount
  });

  // Fetch recommendations
  const { data: recommendations } = useQuery({
    queryKey: ['recommendations', user?.id],
    queryFn: () => api.insights.getRecommendations(user!.id),
    enabled: !!user?.id,
  });

  // Fetch games list
  const { data: games, refetch: refetchGames } = useQuery({
    queryKey: ['games', user?.id],
    queryFn: () => api.games.getForUser(user!.id, { limit: 100 }),
    enabled: !!user?.id,
  });

  useEffect(() => {
    // Handle missing username - redirect to home
    if (!router.isReady) return;
    
    if (!username) {
      toast.error('No username provided. Redirecting to home...');
      router.push('/');
      return;
    }
    
    // Handle user data loading states
    if (userData) {
      setUser(userData);
      setLoading(false);
    } else if (userError) {
      toast.error('Failed to load user data');
      setLoading(false);
      router.push('/');
    } else if (!userLoading && !userData) {
      // Query is enabled but no data and not loading = user not found
      setLoading(false);
    }
  }, [userData, userError, userLoading, username, router]);

  const [isFetching, setIsFetching] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzingGameIds, setAnalyzingGameIds] = useState<Set<number>>(new Set());

  const handleFetchGames = async () => {
    if (!user) return;
    setIsFetching(true);
    try {
      const result = await api.games.fetchRecent(user.id, { days: 10 });
      if (result.games_added === 0) {
        toast('No new games found', { icon: 'ℹ️' });
      } else {
        const method = result.fetch_method === 'days' ? 'from last 10 days' : 'most recent';
        toast.success(`🎉 Fetched ${result.games_added} new games ${method}!`);
        // Refetch games list to show newly fetched games
        refetchGames();
      }
    } catch (error: any) {
      console.error('Error fetching games:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to fetch games from Chess.com';
      toast.error(`❌ ${errorMessage}`);
    } finally {
      setIsFetching(false);
    }
  };

  const handleAnalyzeGames = async (forceReanalysis = false) => {
    if (!user) return;
    setIsAnalyzing(true);
    setAnalysisError(null);
    
    try {
      // Analyze ALL games (not just last 7 days)
      const result = await api.analysis.analyzeGames(user.id, { 
        days: 365, // Use large number to include all games
        forceReanalysis 
      });
      
      if (result.games_queued === 0) {
        // Check if games exist but are already analyzed
        if (userData?.total_games && userData.total_games > 0) {
          toast('✅ All games already analyzed! Sync new games to analyze more.', { 
            icon: '✅',
            duration: 4000 
          });
        } else {
          toast('No games to analyze. Sync games from Chess.com first!', { 
            icon: '🤔' 
          });
        }
        setIsAnalyzing(false);
      } else {
        // Show modal and start polling
        setAnalyzingGamesCount(result.games_queued);
        setShowAnalysisModal(true);
        
        const message = forceReanalysis 
          ? `🔄 Re-analyzing ${result.games_queued} games with fresh analysis!`
          : `🧠 Started AI analysis for ${result.games_queued} games!`;
        toast.success(message, { duration: 3000 });
        
        // Start polling for completion
        startAnalysisPolling();
      }
    } catch (error: any) {
      console.error('Error analyzing games:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to start analysis';
      setAnalysisError(errorMessage);
      toast.error(`❌ ${errorMessage}`);
      setIsAnalyzing(false);
    }
  };

  const startSingleGamePolling = (gameId: number) => {
    let pollCount = 0;
    const maxPolls = 60; // Poll for max 3 minutes
    
    const pollInterval = setInterval(async () => {
      pollCount++;
      
      try {
        // Refetch games to check analysis status
        const updatedGames = await api.games.getForUser(user!.id, { limit: 100 });
        const game = updatedGames.find(g => g.id === gameId);
        
        if (game?.is_analyzed || pollCount >= maxPolls) {
          clearInterval(pollInterval);
          
          // Remove from analyzing set
          setAnalyzingGameIds(prev => {
            const newSet = new Set(prev);
            newSet.delete(gameId);
            return newSet;
          });
          
          // Refetch all data to update dashboard - force refresh
          console.log('🔄 Refetching all data after analysis completion...');
          
          const [gamesResult, userResult, summaryResult] = await Promise.all([
            refetchGames(),
            refetchUserData(),
            refetchAnalysisSummary()
          ]);
          
          console.log('📊 Analysis Summary after refetch:', summaryResult.data);
          console.log('🎮 Games after refetch:', gamesResult.data?.filter(g => g.is_analyzed).length, 'analyzed');
          
          // Force a second refetch after a short delay to ensure backend has committed
          setTimeout(async () => {
            console.log('🔄 Second refetch to ensure data is updated...');
            await refetchAnalysisSummary();
          }, 2000);
          
          if (game?.is_analyzed) {
            toast.success('✅ Game analysis complete! Dashboard updating...', {
              duration: 3000,
              icon: '🎉'
            });
          } else {
            toast('⏳ Analysis is taking longer than expected. Please check back later.', {
              duration: 4000
            });
          }
        }
      } catch (error) {
        console.error('Error polling game status:', error);
        clearInterval(pollInterval);
        setAnalyzingGameIds(prev => {
          const newSet = new Set(prev);
          newSet.delete(gameId);
          return newSet;
        });
      }
    }, 3000); // Poll every 3 seconds
  };

  const handleAnalyzeSingleGame = async (gameId: number) => {
    if (!user) return;
    
    // Add to analyzing set
    setAnalyzingGameIds(prev => new Set(prev).add(gameId));
    
    try {
      const result = await api.analysis.analyzeSingleGame(user.id, gameId, false);
      
      if (result.status === 'queued') {
        toast.success('🧠 Analysis started for this game', { duration: 2000 });
        // Start polling for this game's status
        startSingleGamePolling(gameId);
      } else if (result.status === 'already_analyzed') {
        toast.info('✅ This game is already analyzed', { duration: 2000 });
        setAnalyzingGameIds(prev => {
          const newSet = new Set(prev);
          newSet.delete(gameId);
          return newSet;
        });
      }
    } catch (error: any) {
      console.error('Error analyzing game:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to start analysis';
      toast.error(`❌ ${errorMessage}`);
      setAnalyzingGameIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(gameId);
        return newSet;
      });
    }
  };

  const startAnalysisPolling = () => {
    let pollCount = 0;
    const maxPolls = 60; // Poll for max 5 minutes
    let lastAnalyzedCount = 0;
    
    const pollInterval = setInterval(async () => {
      pollCount++;
      
      try {
        // Refetch games to check analysis status - this updates the UI in real-time
        const gamesResult = await refetchGames();
        const updatedGames = gamesResult.data;
        
        if (updatedGames) {
          const analyzedCount = updatedGames.filter(g => g.is_analyzed).length;
          
          // If a new game was analyzed, refetch summary to update dashboard metrics
          if (analyzedCount > lastAnalyzedCount) {
            console.log(`📊 ${analyzedCount - lastAnalyzedCount} new game(s) analyzed, updating dashboard...`);
            await refetchAnalysisSummary();
            lastAnalyzedCount = analyzedCount;
          }
          
          // If analysis is complete or timeout
          if (pollCount >= maxPolls || analyzedCount >= analyzingGamesCount) {
            clearInterval(pollInterval);
            setIsAnalyzing(false);
            setShowAnalysisModal(false); // Close modal
            
            // Final refetch of all data
            await Promise.all([
              refetchUserData(),
              refetchAnalysisSummary()
            ]);
            
            console.log(`✅ Batch analysis complete: ${analyzedCount} games analyzed`);
            toast.success(`✅ Analysis complete! ${analyzedCount} games analyzed.`, {
              duration: 4000,
              icon: '🎉'
            });
          }
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 3000); // Poll every 3 seconds for faster updates
  };

  const handleAnalysisComplete = () => {
    setShowAnalysisModal(false);
    setIsAnalyzing(false);
    // Refetch all data
    refetchGames();
    refetchUserData();
    toast.success('✅ Analysis complete! Your insights have been updated.', {
      duration: 5000,
      icon: '🎉'
    });
  };

  // Use real recommendations from API or show placeholder message
  const coachingInsights = recommendations || [];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400 mx-auto"></div>
          <p className="text-gray-400 mt-4">Loading your chess insights...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">♔</div>
          <p className="text-gray-400">User not found</p>
          <button
            onClick={() => router.push('/')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <div className="text-4xl">♔</div>
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-white">
                Welcome back, {user?.display_name || user?.chesscom_username}!
              </h1>
            </div>
            {/* Connection Status Indicator */}
            <div className="flex items-center space-x-2 bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
              <div className="w-2 h-2 rounded-full bg-yellow-400"></div>
              <span className="text-sm text-gray-300">
                {userData?.connection_status || 'Public Data Only'}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-gray-300">
              Your chess performance insights and coaching recommendations
            </p>
            {userData && !userData.can_access_private_data && (
              <div className="text-xs text-gray-500 bg-gray-800 px-3 py-1 rounded-full border border-gray-700">
                🔍 Using public Chess.com data
              </div>
            )}
          </div>
        </div>

        {/* Games Summary */}
        {userData && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Total Games Fetched</p>
                <p className="text-2xl font-bold text-white">{userData.total_games || 0}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Games Analyzed</p>
                <p className="text-2xl font-bold text-white">{analysisSummary?.total_games_analyzed || 0}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Status</p>
                <p className="text-sm font-medium text-yellow-400">
                  {analysisSummary?.total_games_analyzed === 0 ? 'Ready for Analysis' : 'Analyzed'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-4 mb-8">
          <button
            onClick={handleFetchGames}
            disabled={isFetching}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
          >
            {isFetching ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Clock className="w-4 h-4" />
            )}
            <span>{isFetching ? 'Syncing...' : 'Sync Recent Games'}</span>
          </button>
          <button
            onClick={() => handleAnalyzeGames(false)}
            disabled={isAnalyzing}
            className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
          >
            {isAnalyzing ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Brain className="w-4 h-4" />
            )}
            <span>{isAnalyzing ? 'Analyzing...' : 'Analyze with AI'}</span>
          </button>
          
          {/* Force Reanalyze button - only show if games are analyzed */}
          {analysisSummary && analysisSummary.total_games_analyzed > 0 && (
            <button
              onClick={() => handleAnalyzeGames(true)}
              disabled={isAnalyzing}
              className="bg-purple-600 text-white px-6 py-3 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
              title="Re-analyze all games (ignores previous analysis)"
            >
              {isAnalyzing ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              ) : (
                <Brain className="w-4 h-4" />
              )}
              <span>Force Re-analyze</span>
            </button>
          )}
          
          {/* Future OAuth Upgrade Button */}
          {userData && userData.connection_type === 'username_only' && (
            <button
              disabled
              className="bg-gray-700 text-gray-400 px-6 py-3 rounded-lg cursor-not-allowed font-medium flex items-center space-x-2 border border-gray-600"
              title="OAuth integration coming soon when Chess.com provides API access"
            >
              <div className="text-sm">🔐</div>
              <span>Upgrade to OAuth</span>
              <div className="text-xs bg-gray-600 px-2 py-1 rounded">
                Future
              </div>
            </button>
          )}
        </div>

        {/* Performance Overview Cards */}
        {analysisSummary && !summaryLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <PerformanceCard
              title="Games Analyzed"
              value={analysisSummary.total_games_analyzed}
              icon={<Trophy className="w-6 h-6" />}
              subtitle="Last 7 days"
            />
            <PerformanceCard
              title="Average Accuracy"
              value={`${analysisSummary.accuracy_percentage?.toFixed(1) || 0}%`}
              change={5.2}
              trend="up"
              icon={<Target className="w-6 h-6" />}
              subtitle="Higher is better"
            />
            <PerformanceCard
              title="ACPL"
              value={analysisSummary.average_acpl?.toFixed(0) || 'N/A'}
              change={-8}
              trend="up"
              icon={<Brain className="w-6 h-6" />}
              subtitle="Lower is better"
            />
            <PerformanceCard
              title="Favorite Opening"
              value={
                analysisSummary.most_played_openings?.[0]?.[0] 
                  ? (analysisSummary.most_played_openings[0][0].length > 20 
                      ? analysisSummary.most_played_openings[0][0].substring(0, 20) + '...' 
                      : analysisSummary.most_played_openings[0][0])
                  : 'N/A'
              }
              icon={<Zap className="w-6 h-6" />}
              subtitle="Most played this week"
            />
          </div>
        )}

        {/* Charts and Insights Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Move Quality Chart */}
          {analysisSummary?.move_quality_breakdown && (
            <MoveQualityChart data={analysisSummary.move_quality_breakdown} />
          )}
          
          {/* Phase Performance */}
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Phase Performance (ACPL)</h3>
              <button
                onClick={() => refetchAnalysisSummary()}
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                title="Refresh data"
              >
                🔄 Refresh
              </button>
            </div>
            {analysisSummary?.total_games_analyzed > 0 && analysisSummary?.phase_performance ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={[
                    { phase: 'Opening', acpl: analysisSummary.phase_performance.opening_acpl || 0 },
                    { phase: 'Middlegame', acpl: analysisSummary.phase_performance.middlegame_acpl || 0 },
                    { phase: 'Endgame', acpl: analysisSummary.phase_performance.endgame_acpl || 0 },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="phase" stroke="#9CA3AF" />
                  <YAxis stroke="#9CA3AF" label={{ value: 'ACPL (Lower is better)', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1F2937', 
                      border: '1px solid #4B5563', 
                      borderRadius: '8px', 
                      color: '#fff' 
                    }}
                    formatter={(value: number) => [value.toFixed(1), 'ACPL']}
                  />
                  <Bar dataKey="acpl" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-500">
                <div className="text-center">
                  <Trophy className="w-12 h-12 mx-auto mb-4 text-gray-600" />
                  <p>Analyze some games to see phase performance</p>
                  <p className="text-xs mt-2">Click "Analyze" on any game below</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Games List */}
        {games && games.length > 0 && (
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 mb-8">
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={() => setGamesCollapsed(!gamesCollapsed)}
                className="flex items-center gap-2 hover:opacity-80 transition-opacity"
              >
                <Trophy className="w-5 h-5 text-blue-400" />
                <h2 className="text-xl font-semibold text-white">Fetched Games</h2>
                <span className="text-sm text-gray-400">{games.length} games</span>
                <span className="text-gray-400 ml-2">
                  {gamesCollapsed ? '▼' : '▲'}
                </span>
              </button>
              <button
                onClick={() => handleAnalyzeGames(false)}
                disabled={isAnalyzing || games.every(g => g.is_analyzed)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                <Brain className="w-4 h-4" />
                {isAnalyzing ? 'Analyzing...' : games.every(g => g.is_analyzed) ? 'All Analyzed' : 'Analyze All Games'}
              </button>
            </div>
            {!gamesCollapsed && (
            <div className="space-y-3">
              {games.map((game) => {
                const userColor = game.white_username?.toLowerCase() === user?.chesscom_username?.toLowerCase() ? 'white' : 'black';
                const opponentUsername = userColor === 'white' ? game.black_username : game.white_username;
                const userResult = userColor === 'white' ? game.white_result : game.black_result;
                const gameResult = userResult === 'win' ? '🎉 Win' : userResult === 'checkmated' || userResult === 'resigned' || userResult === 'timeout' ? '❌ Loss' : '🤝 Draw';
                const resultColor = userResult === 'win' ? 'text-green-400' : userResult === 'checkmated' || userResult === 'resigned' || userResult === 'timeout' ? 'text-red-400' : 'text-gray-400';
                
                return (
                  <div key={game.id} className="bg-gray-700/50 p-4 rounded-lg border border-gray-600 hover:border-gray-500 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <span className="text-lg font-medium text-white">vs {opponentUsername}</span>
                          <span className={`text-sm font-semibold ${resultColor}`}>{gameResult}</span>
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-gray-400">
                          <span>🎮 {game.time_class || 'Unknown'}</span>
                          <span>📅 {game.end_time ? new Date(game.end_time).toLocaleDateString() : 'N/A'}</span>
                          <span>🕐 {game.end_time ? new Date(game.end_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'N/A'}</span>
                        </div>
                      </div>
                      <div className="flex items-center space-x-3">
                        {game.is_analyzed ? (
                          <span className="px-3 py-1 bg-green-600/20 text-green-400 text-xs font-medium rounded-full border border-green-600/30 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            Analyzed
                          </span>
                        ) : analyzingGameIds.has(game.id) ? (
                          <span className="px-3 py-1 bg-blue-600/20 text-blue-400 text-xs font-medium rounded-full border border-blue-600/30 flex items-center gap-1">
                            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-400" />
                            Analyzing...
                          </span>
                        ) : (
                          <button
                            onClick={() => handleAnalyzeSingleGame(game.id)}
                            disabled={isAnalyzing}
                            className="px-3 py-1 bg-purple-600/20 hover:bg-purple-600/40 text-purple-400 text-xs font-medium rounded-full border border-purple-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                          >
                            <Zap className="w-3 h-3" />
                            Analyze
                          </button>
                        )}
                        {game.chesscom_url && (
                          <a
                            href={game.chesscom_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300 text-sm"
                          >
                            View →
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            )}
          </div>
        )}

        {/* Coaching Insights */}
        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 mb-8">
          <div className="flex items-center space-x-2 mb-6">
            <Brain className="w-6 h-6 text-blue-400" />
            <h3 className="text-xl font-semibold text-white">AI Coach Insights</h3>
          </div>
          <div className="space-y-4">
            {coachingInsights.length > 0 ? (
              coachingInsights.map((insight, index) => (
                <CoachingInsightCard
                  key={index}
                  category={insight.category}
                  priority={insight.priority}
                  description={insight.description}
                  improvement={insight.improvement}
                />
              ))
            ) : (
              <div className="flex items-center justify-center py-12 text-gray-500">
                <div className="text-center">
                  <Brain className="w-12 h-12 mx-auto mb-4 text-gray-600" />
                  <p className="text-lg font-medium text-gray-400 mb-2">No insights available yet</p>
                  <p className="text-sm text-gray-500 max-w-md mx-auto">
                    Click <strong>"Analyze with AI"</strong> above to analyze your games and generate personalized coaching insights.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* No Data State */}
        {(!analysisSummary || analysisSummary.total_games_analyzed === 0) && !summaryLoading && (
          <div className="text-center py-12 bg-gray-800 rounded-lg border border-gray-700">
            <div className="text-gray-500 mb-4">
              <Trophy className="w-16 h-16 mx-auto" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Ready to start your chess journey?
            </h3>
            <p className="text-gray-400 mb-6 max-w-md mx-auto">
              Connect your Chess.com account and let our AI analyze your games to provide personalized coaching insights.
            </p>
            <div className="space-x-4">
              <button
                onClick={handleFetchGames}
                disabled={isFetching}
                className="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2 mx-auto"
              >
                {isFetching ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                ) : (
                  <Clock className="w-4 h-4" />
                )}
                <span>{isFetching ? 'Syncing Games...' : 'Sync Your Games'}</span>
              </button>
            </div>
          </div>
        )}
      </div>
      
      {/* Analysis Progress Modal */}
      <AnalysisProgressModal
        isOpen={showAnalysisModal}
        onClose={() => setShowAnalysisModal(false)}
        totalGames={analyzingGamesCount}
        onComplete={handleAnalysisComplete}
      />
    </div>
  );
};

export default Dashboard;
