import React, { useEffect, useState } from 'react';

import { X, Brain, CheckCircle, XCircle, Loader } from 'lucide-react';



interface AnalysisProgressModalProps {

  isOpen: boolean;

  onClose: () => void;

  totalGames: number;

  onComplete?: () => void;

}



export const AnalysisProgressModal: React.FC<AnalysisProgressModalProps> = ({

  isOpen,

  onClose,

  totalGames,

  onComplete

}) => {

  const [status, setStatus] = useState<'analyzing' | 'completed' | 'error'>('analyzing');

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [elapsedTime, setElapsedTime] = useState(0);



  useEffect(() => {

    if (!isOpen) {

      setStatus('analyzing');

      setErrorMessage(null);

      setElapsedTime(0);

      return;

    }



    // Timer for elapsed time

    const timer = setInterval(() => {

      setElapsedTime(prev => prev + 1);

    }, 1000);



    // Estimated time: ~40 seconds per game

    const estimatedTime = totalGames * 40;

    

    // Auto-complete after estimated time (with buffer)

    const autoCompleteTimer = setTimeout(() => {

      setStatus('completed');

      if (onComplete) {

        onComplete();

      }

    }, estimatedTime * 1000 + 5000); // Add 5 second buffer



    return () => {

      clearInterval(timer);

      clearTimeout(autoCompleteTimer);

    };

  }, [isOpen, totalGames, onComplete]);



  const formatTime = (seconds: number) => {

    const mins = Math.floor(seconds / 60);

    const secs = seconds % 60;

    return `${mins}:${secs.toString().padStart(2, '0')}`;

  };



  const estimatedTotalTime = totalGames * 40;

  const progress = Math.min((elapsedTime / estimatedTotalTime) * 100, 95);



  if (!isOpen) return null;



  return (

    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">

      <div className="bg-gray-800 rounded-lg shadow-xl max-w-md w-full border border-gray-700">

        {/* Header */}

        <div className="flex items-center justify-between p-6 border-b border-gray-700">

          <div className="flex items-center gap-3">

            {status === 'analyzing' && <Brain className="w-6 h-6 text-blue-400 animate-pulse" />}

            {status === 'completed' && <CheckCircle className="w-6 h-6 text-green-400" />}

            {status === 'error' && <XCircle className="w-6 h-6 text-red-400" />}

            <h2 className="text-xl font-bold text-white">

              {status === 'analyzing' && 'Analyzing Games'}

              {status === 'completed' && 'Analysis Complete!'}

              {status === 'error' && 'Analysis Error'}

            </h2>

          </div>

          {status !== 'analyzing' && (

            <button

              onClick={onClose}

              className="text-gray-400 hover:text-white transition"

            >

              <X className="w-6 h-6" />

            </button>

          )}

        </div>



        {/* Content */}

        <div className="p-6 space-y-6">

          {status === 'analyzing' && (

            <>

              {/* Progress Info */}

              <div className="text-center">

                <div className="relative inline-flex items-center justify-center">

                  <Loader className="w-16 h-16 text-blue-400 animate-spin" />

                  <Brain className="w-8 h-8 text-blue-300 absolute" />

                </div>

                <p className="text-gray-300 mt-4 text-lg">

                  Analyzing <span className="font-bold text-blue-400">{totalGames}</span> game{totalGames > 1 ? 's' : ''} with Stockfish AI

                </p>

                <p className="text-gray-500 text-sm mt-2">

                  This may take a few minutes...

                </p>

              </div>



              {/* Progress Bar */}

              <div className="space-y-2">

                <div className="flex justify-between text-sm text-gray-400">

                  <span>Progress</span>

                  <span>{Math.round(progress)}%</span>

                </div>

                <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">

                  <div 

                    className="bg-gradient-to-r from-blue-500 to-blue-400 h-3 rounded-full transition-all duration-1000 ease-out"

                    style={{ width: `${progress}%` }}

                  />

                </div>

              </div>



              {/* Time Info */}

              <div className="flex justify-between text-sm">

                <div className="text-gray-400">

                  <span className="text-gray-500">Elapsed: </span>

                  <span className="font-mono text-blue-400">{formatTime(elapsedTime)}</span>

                </div>

                <div className="text-gray-400">

                  <span className="text-gray-500">Est. Total: </span>

                  <span className="font-mono text-blue-400">{formatTime(estimatedTotalTime)}</span>

                </div>

              </div>



              {/* Info */}

              <div className="bg-blue-900 bg-opacity-30 border border-blue-700 rounded-lg p-4">

                <p className="text-blue-200 text-sm">

                  <strong className="text-blue-300">💡 Tip:</strong> Analysis runs in the background. You can close this window and the analysis will continue.

                </p>

              </div>

            </>

          )}



          {status === 'completed' && (

            <>

              <div className="text-center">

                <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-4" />

                <p className="text-xl font-bold text-white mb-2">

                  Analysis Complete! 🎉

                </p>

                <p className="text-gray-400">

                  Successfully analyzed {totalGames} game{totalGames > 1 ? 's' : ''}

                </p>

              </div>



              <button

                onClick={() => {

                  if (onComplete) onComplete();

                  onClose();

                }}

                className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg transition"

              >

                View Results

              </button>

            </>

          )}



          {status === 'error' && errorMessage && (

            <>

              <div className="text-center">

                <XCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />

                <p className="text-xl font-bold text-white mb-2">

                  Analysis Failed

                </p>

                <div className="bg-red-900 bg-opacity-30 border border-red-700 rounded-lg p-4 mt-4">

                  <p className="text-red-200 text-sm">

                    <strong className="text-red-300">Error:</strong> {errorMessage}

                  </p>

                </div>

              </div>



              <button

                onClick={onClose}

                className="w-full bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-lg transition"

              >

                Close

              </button>

            </>

          )}

        </div>

      </div>

    </div>

  );

};

