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
