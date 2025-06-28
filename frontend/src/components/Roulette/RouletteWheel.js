import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import './RouletteWheel.css';

const RouletteWheel = ({ gameState }) => {
  const [rotation, setRotation] = useState(0);
  const [isSpinning, setIsSpinning] = useState(false);

  const sectors = [
    { number: 0, color: 'green' },
    { number: 1, color: 'red' },
    { number: 2, color: 'black' },
    { number: 3, color: 'red' },
    { number: 4, color: 'black' },
    { number: 5, color: 'red' },
    { number: 6, color: 'black' },
    { number: 7, color: 'red' },
    { number: 8, color: 'black' },
    { number: 9, color: 'red' },
    { number: 10, color: 'black' },
    { number: 11, color: 'red' },
    { number: 12, color: 'black' },
    { number: 13, color: 'red' },
    { number: 14, color: 'black' }
  ];

  const sectorAngle = 360 / 15; // 24 degrees per sector

  useEffect(() => {
    if (gameState.phase === 'spinning') {
      setIsSpinning(true);
    } else if (gameState.phase === 'result' && gameState.result) {
      // Calculate the final rotation based on winning number
      const winningNumber = gameState.result.number;
      const targetAngle = (winningNumber * sectorAngle) + (sectorAngle / 2);
      const spins = 5; // Number of full spins
      const finalRotation = (spins * 360) + (360 - targetAngle);
      
      setRotation(prev => prev + finalRotation);
      setIsSpinning(false);
    }
  }, [gameState.phase, gameState.result]);

  const getSectorColor = (color) => {
    switch (color) {
      case 'red': return '#e74c3c';
      case 'black': return '#2c3e50';
      case 'green': return '#27ae60';
      default: return '#2c3e50';
    }
  };

  return (
    <div className="roulette-container">
      <div className="roulette-pointer">▼</div>
      
      <motion.div 
        className="roulette-wheel"
        animate={{ rotate: rotation }}
        transition={{ 
          duration: isSpinning ? 4 : 0,
          ease: "easeOut"
        }}
      >
        <svg width="400" height="400" viewBox="0 0 400 400">
          <circle cx="200" cy="200" r="180" fill="#1a1a1a" stroke="#333" strokeWidth="4"/>
          
          {sectors.map((sector, index) => {
            const startAngle = (index * sectorAngle - 90) * (Math.PI / 180);
            const endAngle = ((index + 1) * sectorAngle - 90) * (Math.PI / 180);
            
            const x1 = 200 + 160 * Math.cos(startAngle);
            const y1 = 200 + 160 * Math.sin(startAngle);
            const x2 = 200 + 160 * Math.cos(endAngle);
            const y2 = 200 + 160 * Math.sin(endAngle);
            
            const largeArcFlag = sectorAngle > 180 ? 1 : 0;
            
            const pathData = [
              `M 200 200`,
              `L ${x1} ${y1}`,
              `A 160 160 0 ${largeArcFlag} 1 ${x2} ${y2}`,
              `Z`
            ].join(' ');

            // Calculate text position
            const textAngle = (index * sectorAngle + sectorAngle / 2 - 90) * (Math.PI / 180);
            const textX = 200 + 130 * Math.cos(textAngle);
            const textY = 200 + 130 * Math.sin(textAngle);

            return (
              <g key={sector.number}>
                <path
                  d={pathData}
                  fill={getSectorColor(sector.color)}
                  stroke="#fff"
                  strokeWidth="2"
                />
                <text
                  x={textX}
                  y={textY}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="white"
                  fontSize="14"
                  fontWeight="bold"
                  transform={`rotate(${index * sectorAngle + sectorAngle / 2}, ${textX}, ${textY})`}
                >
                  {sector.number}
                </text>
              </g>
            );
          })}
          
          {/* Center circle */}
          <circle cx="200" cy="200" r="20" fill="#333" stroke="#fff" strokeWidth="2"/>
        </svg>
      </motion.div>

      {gameState.result && gameState.phase === 'result' && (
        <div className="result-display">
          <div className={`result-number ${gameState.result.color}`}>
            {gameState.result.number}
          </div>
          <div className="result-text">
            Winner: {gameState.result.color.toUpperCase()}
          </div>
        </div>
      )}
    </div>
  );
};

export default RouletteWheel;
