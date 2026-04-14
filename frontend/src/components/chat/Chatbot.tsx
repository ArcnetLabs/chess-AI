/**
 * Main Chatbot Component
 * Combines ChatbotIcon and ChatWindow
 */

import React from 'react';
import { ChatbotIcon } from './ChatbotIcon';
import { ChatWindow } from './ChatWindow';

export const Chatbot: React.FC = () => {
  return (
    <>
      <ChatbotIcon />
      <ChatWindow />
    </>
  );
};

export default Chatbot;
