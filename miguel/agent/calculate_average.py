def calculateAverage(numbersList):
    if not numbersList:
        return 0
    return sum(numbersList) / len(numbersList)

# Test cases
if __name__ == "__main__":
    print(f"Average of [1, 2, 3, 4, 5]: {calculateAverage([1, 2, 3, 4, 5])}")
    print(f"Average of [10, 20, 30]: {calculateAverage([10, 20, 30])}")
    print(f"Average of []: {calculateAverage([])}")
    print(f"Average of [7]: {calculateAverage([7])}")