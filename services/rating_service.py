import json
import os
import discord

class RatingService:
    def __init__(self, ratings_file='ratings.json'):
        self.ratings_file = ratings_file
        self.message_ratings = {}
        self.channel_titles = {}
        self.load_ratings()

    def load_ratings(self):
        if os.path.exists(self.ratings_file):
            with open(self.ratings_file, 'r') as f:
                data = json.load(f)
                # Ensure IDs are integers
                self.message_ratings = {
                    int(msg_id): {
                        'ratings': {int(user_id): rating for user_id, rating in info['ratings'].items()},
                        'average': info['average'],
                        'num_ratings': info['num_ratings']
                    }
                    for msg_id, info in data.get('ratings', {}).items()
                }
                self.channel_titles = data.get('titles', {})

    def save_ratings(self):
        with open(self.ratings_file, 'w') as f:
            json.dump({
                'ratings': {
                    str(msg_id): {
                        'ratings': {str(user_id): rating for user_id, rating in info['ratings'].items()},
                        'average': info['average'],
                        'num_ratings': info['num_ratings']
                    }
                    for msg_id, info in self.message_ratings.items()
                },
                'titles': self.channel_titles
            }, f)

    def add_rating(self, message_id: int, user_id: int, rating: int) -> str:
        if message_id not in self.message_ratings:
            self.message_ratings[message_id] = {'ratings': {}, 'average': 0, 'num_ratings': 0}

        already_voted = user_id in self.message_ratings[message_id]['ratings']
        
        if already_voted:
            old_rating = self.message_ratings[message_id]['ratings'][user_id]
            self.message_ratings[message_id]['ratings'][user_id] = rating
            msg = f"You changed your rating from {old_rating} ⭐️ to {rating} ⭐️!"
        else:
            self.message_ratings[message_id]['ratings'][user_id] = rating
            self.message_ratings[message_id]['num_ratings'] += 1
            msg = f'You gave {rating} ⭐️ for this toybox!'

        self.update_average_rating(message_id)
        self.save_ratings()
        return msg

    def update_average_rating(self, message_id: int):
        ratings = self.message_ratings[message_id]['ratings'].values()
        if ratings:
            average = sum(ratings) / len(ratings)
            self.message_ratings[message_id]['average'] = average

    def get_average_rating(self, message_id: int) -> float:
        return self.message_ratings.get(message_id, {}).get('average', 0)

    def get_star_rating(self, avg_rating: float) -> str:
        full_stars = int(avg_rating)
        round_up = (avg_rating - full_stars) >= 0.6
        return "⭐️" * (full_stars + (1 if round_up else 0))

# Global instance
rating_service = RatingService()
