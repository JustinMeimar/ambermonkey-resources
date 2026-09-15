function sumTo(limit) {
  let sum = 0;
  for (let i = 0; i < limit; i++) {
    sum += i;
  }
  return sum;
}

let result = 0;
for (let i = 0; i < 200; i++) {
  result = sumTo(10000);
}

print(`ambermonkey-smoke: ${result}`);
