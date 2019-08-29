# -*- coding: utf-8 -*-

def get_scheduler(lr_steps: dict):
    def scheduler(epoch):
        for step in sorted(lr_steps)[::-1]:
            if epoch >= step:
                lr = float(lr_steps[step])
                print('{} learning rate {:.2e}'.format(['Set', 'Keep'][epoch > step], lr))
                break
        return lr

    return scheduler
