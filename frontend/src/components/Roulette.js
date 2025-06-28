import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import './Roulette.css';

const Roulette = ({ isSpinning, result }) => {
  const [rotation, setRotation] = useState(0);
  const [sectors] = useState(() => {
    const sectorList = [];
    
    // Red sectors (1-7)
    for (let i = 1; i <= 7; i++) {
      sectorList.push({ number: i, color: 'red' });
    }
    
    // Black sectors (8-14)
    for (let i = 8; i <= 14; i++) {
      sectorList.push({ number: i, color: 'black' });
    }
    
    // Green sector (0)
    sectorList.push({ number: 0, color: 'green' });
    
    return sectorList;
  });

  useEffect(() => {
    if (isSpinning && result) {
      // Find the target sector
      const targetIndex = sectors.findIndex(s => 
        s.number === result.number && s.color.toLowerCase() === result.color.toLowerCase()
      );
      
      // Calculate target rotation
      const sectorAngle = 360 / 15; // 24 degrees per sector
      const targetAngle = targetIndex * sectorAngle;
      
      // Add multiple full rotations for spinning effect
      const spins = 5 + Math.random() * 3; // 5-8 full rotations
      const finalRotation = (spins * 360) + targetAngle;
      
      setRotation(finalRotation);
    }
  }, [isSpinning, result, sectors]);

  const sectorAngle = 360 / 15;

  return (
    <div className="roulette-container">
      <div className="roulette-pointer">▼</div>
      <motion.div
        className="roulette-wheel"
        animate={{ rotate: rotation }}
        transition={{
          duration: isSpinning ? 4 : 0,
          ease: [0.23, 1, 0.32, 1]
        }}
      >
        <svg width="400" height="400" viewBox="0 0 400 400">
          <circle cx="200" cy="200" r="190" fill="#8B4513" stroke="#654321" strokeWidth="4" />
          {sectors.map((sector, index) => {
            const startAngle = (index * sectorAngle - 90) * (Math.PI / 180);
            const endAngle = ((index + 1) * sectorAngle - 90) * (Math.PI / 180);
            
            const largeArcFlag = sectorAngle > 180 ? 1 : 0;
            
            const x1 = 200 + 170 * Math.cos(startAngle);
            const y1 = 200 + 170 * Math.sin(startAngle);
            const x2 = 200 + 170 * Math.cos(endAngle);
            const y2 = 200 + 170 * Math.sin(endAngle);
            
            const textAngle = (startAngle + endAngle) / 2;
            const textX = 200 + 130 * Math.cos(textAngle);
            const textY = 200 + 130 * Math.sin(textAngle);
            
            return (
              <g key={index}>
                <path
                  d={`M 200 200 L ${x1} ${y1} A 170 170 0 ${largeArcFlag} 1 ${x2} ${y2} Z`}
                  fill={sector.color}
                  stroke="white"
                  strokeWidth="2"
                />
                <text
                  x={textX}
                  y={textY}
                  fill="white"
                  fontSize="20"
                  fontWeight="bold"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {sector.number}
                </text>
              </g>
            );
          })}
          <circle cx="200" cy="200" r="20" fill="#333" />
        </svg>
      </motion.div>
      
      {result && (
        <div className="result-display">
          <div className={`result-number ${result.color.toLowerCase()}`}>
            {result.number}
          </div>
          <div className="result-color">
            {result.color}
          </div>
        </div>
      )}
    </div>
  );
};

export default Roulette;
